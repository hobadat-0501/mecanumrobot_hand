"""T20: gesture mode on the app server - mode/hb to the robot, vision link, /video, staff relay."""
import asyncio
import json
import struct
import time
from http import HTTPStatus

import httpx
import pytest
from websockets.asyncio.server import serve

from app_server.control import ControlSession
from app_server.telemetry import Telemetry

from test_server import (
    ORIGIN,
    OPERATOR_TOKEN,
    arm_as_driver,
    operator,
    robot,  # noqa: F401  (fixture)
    robot_state,
    running_app,
    send,
    state_where,
    wait_until,
)

VISION_TOKEN = "vision-test-token"
IDLE = {"seq": 1, "vx": 0.0, "vy": 0.0, "wz": 0.0}


# ---------------------------------------------------------------- ControlSession

def _session(clock=None):
    s = ControlSession(OPERATOR_TOKEN, [ORIGIN], clock or time.monotonic)
    assert s.connect("a", ORIGIN)
    assert s.hello("a", OPERATOR_TOKEN)
    return s


def test_mode_needs_driver_armed_and_bool():
    s = _session()
    assert not s.set_mode("a", True)  # not armed
    s.arm("a", True)
    assert not s.set_mode("a", "yes") and not s.set_mode("a", 1)
    s.connect("b", ORIGIN)
    assert not s.set_mode("b", True)  # viewer
    assert s.set_mode("a", True) and s.gesture
    assert s.snapshot()["mode"] == "gesture"
    assert s.set_mode("a", False) and not s.gesture


def test_disarm_and_driver_loss_turn_mode_off():
    s = _session()
    s.arm("a", True)
    s.set_mode("a", True)
    s.arm("a", False)
    assert not s.gesture
    s.arm("a", True)
    s.set_mode("a", True)
    s.disconnect("a")
    assert not s.gesture


def test_nonzero_manual_cmd_turns_mode_off_zero_does_not():
    s = _session()
    s.arm("a", True)
    s.set_mode("a", True)
    s.handle_cmd_vel("a", {"type": "cmd_vel", "seq": 1, "vx": 0, "vy": 0, "wz": 0})
    assert s.gesture
    s.handle_cmd_vel("a", {"type": "cmd_vel", "seq": 2, "vx": 0.1, "vy": 0, "wz": 0})
    assert not s.gesture


def test_robot_mode_off_has_a_grace_period():
    now = [100.0]
    s = _session(lambda: now[0])
    s.arm("a", True)
    s.set_mode("a", True)
    assert not s.robot_mode_off()
    now[0] += 1.1
    assert s.robot_mode_off() and not s.gesture
    assert not s.robot_mode_off()


def test_telemetry_passes_robot_gesture_report_without_scaling():
    t = Telemetry(speed_scale=1.89)
    msg = robot_state()
    msg.update(mode="gesture", src="vision", vision={"link": True},
               lidar_gate={"blocked": True, "min_m": 0.31})
    t.on_robot_state(msg)
    sess = {"armed": True, "has_driver": True, "cmd": {"vx": 0, "vy": 0, "wz": 0}, "mode": "gesture"}
    state = t.build_state(sess, True)
    assert state["gesture"]["lidar_gate"] == {"blocked": True, "min_m": 0.31}
    assert state["gesture"]["mode"] == "gesture" and state["session"]["mode"] == "gesture"
    t.clear_robot()
    assert t.build_state(sess, False)["gesture"] is None


# ---------------------------------------------------------------- fake vision agent

class FakeVision:
    def __init__(self):
        self.received = []
        self.conns = []
        self.port = None
        self._server = None

    def _process_request(self, connection, request):
        if request.headers.get("Authorization") != "Bearer " + VISION_TOKEN:
            return connection.respond(HTTPStatus.UNAUTHORIZED, "no\n")
        return None

    async def _handler(self, conn):
        self.conns.append(conn)
        try:
            async for message in conn:
                self.received.append(json.loads(message))
        except Exception:
            pass

    async def start(self):
        self._server = await serve(self._handler, "127.0.0.1", 0, process_request=self._process_request)
        self.port = self._server.sockets[0].getsockname()[1]

    async def stop(self):
        self._server.close()
        await self._server.wait_closed()

    @property
    def url(self):
        return "ws://127.0.0.1:%d/ws" % self.port

    async def push_state(self, **extra):
        data = {"t": "vision_state", "mode": True, "state": "GESTURE", "user": "u1",
                "gesture": None, "cmd": {"active": True, "vx": 9.9}, "guide": None, "fps": 20,
                "temps": {}, "events": [], **extra}
        for conn in self.conns:
            await conn.send(json.dumps(data))

    async def push_frame(self, seq, jpeg):
        for conn in self.conns:
            await conn.send(struct.pack("<BBIQ", 3, 1, seq, 0) + jpeg)


@pytest.fixture
async def vision():
    v = FakeVision()
    await v.start()
    yield v
    await v.stop()


def _modes(robot):
    return [m for m in robot.received if m.get("t") == "mode"]


def _hbs(robot):
    return [m for m in robot.received if m.get("t") == "hb"]


# ---------------------------------------------------------------- end to end with a fake robot

async def test_mode_on_needs_arm_then_sends_mode_and_heartbeats(robot):
    async with running_app(robot.url) as app:
        async with operator(app) as ws:
            await wait_until(lambda: app.runtime.link.connected)
            await state_where(ws, lambda s: s["session"]["role"] == "driver")
            await send(ws, t="mode", gesture=True)  # not armed
            await asyncio.sleep(0.2)
            assert _modes(robot) == []
            await arm_as_driver(ws, app)
            await send(ws, t="mode", gesture=True)
            await state_where(ws, lambda s: s["session"]["mode"] == "gesture")
            await wait_until(lambda: len(_hbs(robot)) >= 3)
            assert _modes(robot)[0]["gesture"] is True
            seqs = [m["seq"] for m in _hbs(robot)]
            assert seqs == sorted(set(seqs))
            await send(ws, t="arm", on=False)  # disarm = mode off + zero
            await state_where(ws, lambda s: s["session"]["mode"] == "manual")
            await wait_until(lambda: _modes(robot)[-1]["gesture"] is False)
            assert robot.cmds()[-1]["vx"] == 0


async def test_no_heartbeat_when_mode_off_and_no_velocity_in_mode_or_hb(robot):
    async with running_app(robot.url) as app:
        async with operator(app) as ws:
            await arm_as_driver(ws, app)
            await asyncio.sleep(0.5)
            assert _hbs(robot) == []
            await send(ws, t="mode", gesture=True)
            await wait_until(lambda: len(_hbs(robot)) >= 1)
            for m in _modes(robot) + _hbs(robot):
                assert not {"vx", "vy", "wz"} & set(m)


async def test_viewer_cannot_set_mode(robot):
    async with running_app(robot.url) as app:
        async with operator(app) as driver:
            await arm_as_driver(driver, app)
            async with operator(app, drive=False) as viewer:
                await send(viewer, t="mode", gesture=True)
                await asyncio.sleep(0.3)
            assert _modes(robot) == []


async def test_server_follows_robot_turning_the_mode_off(robot):
    async with running_app(robot.url) as app:
        async with operator(app) as ws:
            await arm_as_driver(ws, app)
            await send(ws, t="mode", gesture=True)
            await state_where(ws, lambda s: s["session"]["mode"] == "gesture")
            await asyncio.sleep(1.2)  # past the grace period
            await robot.send_state({**robot_state(), "mode": "manual", "src": "none"})
            await state_where(ws, lambda s: s["session"]["mode"] == "manual", timeout=4.0)


async def test_driver_disconnect_sends_mode_off_and_zero(robot):
    async with running_app(robot.url) as app:
        async with operator(app) as ws:
            await arm_as_driver(ws, app)
            await send(ws, t="mode", gesture=True)
            await wait_until(lambda: len(_modes(robot)) == 1)
        await wait_until(lambda: _modes(robot)[-1]["gesture"] is False and len(_modes(robot)) >= 2)


async def test_robot_gesture_report_reaches_the_web(robot):
    async with running_app(robot.url) as app:
        async with operator(app) as ws:
            await wait_until(lambda: app.runtime.link.connected)
            await robot.send_state({**robot_state(), "mode": "gesture", "src": "vision",
                                    "vision": {"link": True},
                                    "lidar_gate": {"blocked": False, "min_m": None}})
            s = await state_where(ws, lambda s: s.get("gesture") is not None)
            assert s["gesture"]["src"] == "vision"


# ---------------------------------------------------------------- vision link, /video, staff relay

async def test_vision_disabled_without_token(robot):
    async with running_app(robot.url) as app:
        async with operator(app) as ws:
            s = await state_where(ws, lambda s: True)
            assert s["vision"]["enabled"] is False and s["vision"]["link"] is False


async def test_vision_state_is_whitelisted_and_has_no_velocity(robot, vision):
    env = {"VISION_WS_URL": vision.url, "VISION_LINK_TOKEN": VISION_TOKEN}
    async with running_app(robot.url, extra_env=env) as app:
        async with operator(app) as ws:
            await wait_until(lambda: app.runtime.vision.connected)
            await vision.push_state(secret="x", vx=1.0)
            s = await state_where(ws, lambda s: s["vision"]["state"] is not None)
            v = s["vision"]["state"]
            assert v["state"] == "GESTURE" and v["cmd_active"] is True
            assert "cmd" not in v and "vx" not in v and "secret" not in v


async def test_staff_commands_only_from_driver_and_known_types(robot, vision):
    env = {"VISION_WS_URL": vision.url, "VISION_LINK_TOKEN": VISION_TOKEN}
    async with running_app(robot.url, extra_env=env) as app:
        async with operator(app) as driver:
            await wait_until(lambda: app.runtime.vision.connected)
            await state_where(driver, lambda s: s["session"]["role"] == "driver")
            async with operator(app, drive=False) as viewer:
                await send(viewer, t="staff_list")
                await asyncio.sleep(0.2)
            await send(driver, t="staff_list")
            await send(driver, t="drive_forward", vx=1)
            await wait_until(lambda: len(vision.received) >= 1)
            await asyncio.sleep(0.2)
            assert [m["t"] for m in vision.received] == ["staff_list"]


async def test_video_needs_cookie_from_a_valid_hello(robot, vision):
    env = {"VISION_WS_URL": vision.url, "VISION_LINK_TOKEN": VISION_TOKEN}
    async with running_app(robot.url, extra_env=env) as app:
        async with httpx.AsyncClient() as http:
            assert (await http.get(app.http_url + "/video")).status_code == 403
            bad = await http.post(app.http_url + "/video/session", json={"nonce": "x"},
                                  headers={"Origin": ORIGIN})
            assert bad.status_code == 403
            async with operator(app) as ws:
                s = await state_where(ws, lambda s: s["session"].get("video_nonce"))
                nonce = s["session"]["video_nonce"]
                evil = await http.post(app.http_url + "/video/session", json={"nonce": nonce},
                                       headers={"Origin": "http://evil.example"})
                assert evil.status_code == 403
                ok = await http.post(app.http_url + "/video/session", json={"nonce": nonce},
                                     headers={"Origin": ORIGIN})
                assert ok.status_code == 200 and "video_session" in http.cookies
                assert ok.headers["access-control-allow-origin"] == ORIGIN
                again = await http.post(app.http_url + "/video/session", json={"nonce": nonce},
                                        headers={"Origin": ORIGIN})
                assert again.status_code == 403  # single use
                await wait_until(lambda: app.runtime.vision.connected)
                await vision.push_frame(1, b"\xff\xd8JPEGDATA")
                await wait_until(lambda: app.runtime.vision.frame is not None)
                async with http.stream("GET", app.http_url + "/video") as r:
                    assert r.status_code == 200
                    assert r.headers["content-type"].startswith("multipart/x-mixed-replace")
                    body = b""
                    async for chunk in r.aiter_bytes():
                        body += chunk
                        if b"JPEGDATA" in body:
                            break
                    assert b"image/jpeg" in body

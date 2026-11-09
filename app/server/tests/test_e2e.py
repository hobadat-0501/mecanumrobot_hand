"""T14 end-to-end tests, in one process, no browser.

Real pieces: RobotServer + CmdVelWriter (a real thread) + SimulatedStm32/SimulatedLidar on
127.0.0.1 with an ephemeral port, the real app server (`app_server.main.create_app` under uvicorn,
ephemeral port) and plain `websockets` clients standing in for the browser.

Timings use time.monotonic(). Every measured number is printed as a line starting with "[e2e]";
run with `pytest app/server/tests/test_e2e.py -s` to see them. To stay robust under CPU load a
timing check repeats (3 trials; the median must meet the bound and the worst must stay within
twice the bound) instead of trusting one sample.
"""

import asyncio
import dataclasses
import json
import math
import statistics
import struct
import time
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest
import uvicorn
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed, InvalidStatus

from app_server.config import load_settings
from app_server.main import create_app
from robot_agent.drive import CmdVelWriter
from robot_agent.server import RobotServer
from robot_agent.sim import SimulatedLidar, SimulatedStm32

LINK_TOKEN = "e2e-link-token"
OPERATOR_TOKEN = "e2e-operator-token"
ORIGIN = "http://100.119.83.63:3000"
FACTOR = 1.89  # only used here to prove that nothing on the web side carries it

LOOP_P95_BOUND_S = 0.150  # NFR-02: cmd_vel -> last_cmd_seq in state
STOP_BOUND_S = 0.300  # NFR-02 / SAF-03: event -> zero at the STM32 (operator gone, link cut, disarm)
SILENCE_DEADLINE_S = 0.250  # SAF-03: no command for 250 ms
SILENCE_BOUND_S = SILENCE_DEADLINE_S + 0.300  # last command -> zero when the sender goes quiet
FLAG_BOUND_S = 0.500  # SAF-05: stop flag or stale telemetry -> zero


# ---- the robot side ----


class E2eStm(SimulatedStm32):
    """SimulatedStm32 that logs every velocity written and can fake a stop flag or old telemetry."""

    def __init__(self):
        super().__init__()
        self.log = []  # (time.monotonic(), vx, vy, wz) for each successful write, wire units
        self.flag_stop = 0
        self.telemetry_age_ns = 0

    @property
    def latest(self):
        sample = SimulatedStm32.latest.fget(self)
        if sample is None:
            return None
        return dataclasses.replace(
            sample, flag_stop=self.flag_stop, t_ns=sample.t_ns - self.telemetry_age_ns
        )

    def send_velocity(self, vx_mps, vy_mps, wz_radps):
        super().send_velocity(vx_mps, vy_mps, wz_radps)
        self.log.append((time.monotonic(), float(vx_mps), float(vy_mps), float(wz_radps)))


def is_zero(entry):
    return entry[1] == 0.0 and entry[2] == 0.0 and entry[3] == 0.0


def nonzero_entries(stm):
    return [e for e in list(stm.log) if not is_zero(e)]


async def wait_until(condition, timeout=3.0, step=0.005):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return
        await asyncio.sleep(step)
    raise AssertionError("condition not met in time")


async def zero_latency(stm, t0, timeout=2.0):
    """Seconds from t0 until the first zero written to the STM32 simulator at or after t0."""
    deadline = time.monotonic() + timeout
    while True:
        for entry in list(stm.log):
            if entry[0] >= t0 and is_zero(entry):
                return entry[0] - t0
        if time.monotonic() > deadline:
            raise AssertionError("no zero reached the STM32 simulator")
        await asyncio.sleep(0.002)


async def assert_stays_zero(stm, t_zero, seconds=0.3):
    """After the first zero at t_zero nothing but zero is written for `seconds`."""
    await asyncio.sleep(seconds)
    late = [e for e in list(stm.log) if e[0] > t_zero and not is_zero(e)]
    assert late == [], "motion resumed after the stop: %r" % (late[:3],)


def assert_moving(stm):
    """The simulator is being driven right now: the newest write is fresh and not zero."""
    last = stm.log[-1]
    assert not is_zero(last) and time.monotonic() - last[0] < 0.2, "the robot is not moving"


async def run_trials(label, trial, bound, *, floor=0.0, trials=3):
    results = []
    for _ in range(trials):
        results.append(await trial())
    median = statistics.median(results)
    shown = ", ".join("%.0f ms" % (x * 1000) for x in results)
    print("[e2e] %s: %s | median %.0f ms, bound %.0f ms" % (label, shown, median * 1000, bound * 1000))
    assert median <= bound, (label, results)
    assert max(results) <= 2 * bound, (label, results)
    assert min(results) >= floor, (label, results)
    return results


# ---- the rig: robot server + simulators + app server ----


@asynccontextmanager
async def running_app(robot_url, link_token):
    settings = load_settings(
        {
            "ROBOT_LINK_TOKEN": link_token,
            "OPERATOR_TOKEN": OPERATOR_TOKEN,
            "ROBOT_WS_URL": robot_url,
            "APP_ALLOWED_ORIGINS": ORIGIN,
        }
    )
    app = create_app(settings, backoff_initial_s=0.02, backoff_max_s=0.1)
    server = uvicorn.Server(
        uvicorn.Config(
            app,
            host="127.0.0.1",
            port=0,
            log_level="warning",
            lifespan="on",
            timeout_graceful_shutdown=2,
        )
    )
    task = asyncio.ensure_future(server.serve())
    try:
        deadline = time.monotonic() + 5.0
        while not server.started:
            if task.done():
                task.result()
            if time.monotonic() > deadline:
                raise AssertionError("app server did not start")
            await asyncio.sleep(0.01)
        port = server.servers[0].sockets[0].getsockname()[1]
        yield SimpleNamespace(ws_url="ws://127.0.0.1:%d/ws/operator" % port, runtime=app.state.runtime)
    finally:
        server.should_exit = True
        await asyncio.wait_for(task, 10)


@asynccontextmanager
async def rig(*, deadman_s=0.25, app_link_token=LINK_TOKEN, with_app=True):
    """The robot side always; the app server only when with_app."""
    stm = E2eStm()
    stm.start()
    lidar = SimulatedLidar()
    lidar.start()
    writer = CmdVelWriter(stm, motion_enabled=True, deadman_s=deadman_s)
    writer.start()
    health = {"ok": True, "state": "ok", "error": None, "restarts": 0}
    robot = RobotServer(
        token=LINK_TOKEN,
        writer=writer,
        stm=stm,
        devices=lambda: {"stm": health, "lidar": health},
        lidar=lidar,
    )
    port = await robot.start("127.0.0.1", 0)
    robot_url = "ws://127.0.0.1:%d/ws" % port
    try:
        if with_app:
            async with running_app(robot_url, app_link_token) as app:
                yield SimpleNamespace(stm=stm, writer=writer, robot=robot, robot_url=robot_url, app=app)
        else:
            yield SimpleNamespace(stm=stm, writer=writer, robot=robot, robot_url=robot_url, app=None)
    finally:
        await robot.close()
        writer.stop()
        lidar.stop()
        stm.stop()


# ---- the web side: a plain websockets client that records everything it receives ----


class Web:
    def __init__(self, ws):
        self.ws = ws
        self.texts = []  # every text frame, as received
        self.frames = []  # every binary frame
        self.states = []  # (time.monotonic() at receipt, decoded state)
        self.task = asyncio.ensure_future(self._read())

    async def _read(self):
        try:
            async for message in self.ws:
                now = time.monotonic()
                if isinstance(message, bytes):
                    self.frames.append(message)
                    continue
                self.texts.append(message)
                data = json.loads(message)
                if data.get("t") == "state":
                    self.states.append((now, data))
        except ConnectionClosed:
            pass

    async def send(self, **message):
        await self.ws.send(json.dumps(message))

    async def send_raw(self, text):
        await self.ws.send(text)

    async def wait_state(self, predicate, *, since=0, timeout=3.0):
        """(receipt time, state) of the first state at index >= since that satisfies predicate."""
        deadline = time.monotonic() + timeout
        index = since
        while True:
            while index < len(self.states):
                stamp, state = self.states[index]
                index += 1
                if predicate(state):
                    return stamp, state
            if time.monotonic() > deadline:
                raise AssertionError("no matching state received")
            await asyncio.sleep(0.002)


@asynccontextmanager
async def web_connect(app, *, origin=ORIGIN):
    async with connect(app.ws_url, origin=origin, open_timeout=5) as ws:
        web = Web(ws)
        try:
            yield web
        finally:
            web.task.cancel()
            await asyncio.gather(web.task, return_exceptions=True)


async def wait_link(app):
    await wait_until(lambda: app.runtime.link.connected)


async def become_driver_and_arm(web, app, *, arm=True):
    await wait_link(app)
    since = len(web.states)
    await web.send(t="hello", token=OPERATOR_TOKEN)
    await web.wait_state(
        lambda s: s["session"]["role"] == "driver" and s["link"]["robot"], since=since
    )
    if arm:
        since = len(web.states)
        await web.send(t="arm", on=True)
        await web.wait_state(lambda s: s["session"]["armed"], since=since)


async def drive_for(web, seq, seconds, vx=0.189):
    """Send cmd_vel at 20 Hz for `seconds`. Returns (last seq, monotonic time of the last send)."""
    end = time.monotonic() + seconds
    sent_at = time.monotonic()
    while True:
        seq += 1
        sent_at = time.monotonic()
        await web.send(t="cmd_vel", seq=seq, vx=vx, vy=0.0, wz=0.0, src="kbd")
        if sent_at + 0.05 >= end:
            return seq, sent_at
        await asyncio.sleep(0.05)


@asynccontextmanager
async def bare_app_server(robot_url):
    """A plain client playing the app server on the robot link. It reads (and ignores) the state
    stream, as the real one does; an unread stream would stall the close handshake."""

    async def drain(ws):
        try:
            async for _ in ws:
                pass
        except ConnectionClosed:
            pass

    async with connect(robot_url, additional_headers={"Authorization": "Bearer " + LINK_TOKEN}) as ws:
        reader = asyncio.ensure_future(drain(ws))
        try:
            yield ws
        finally:
            reader.cancel()
            await asyncio.gather(reader, return_exceptions=True)


def percentile(values, p):
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, max(0, math.ceil(p * len(ordered)) - 1))]


# ======================================================================================
# (a) SAF-01: units
# ======================================================================================


def numbers_below(value, path=()):
    """Yield (path, key-or-None, number-or-None): every dict key and every numeric leaf."""
    if isinstance(value, dict):
        for key, item in value.items():
            yield path, key, None
            yield from numbers_below(item, path + (key,))
    elif isinstance(value, list):
        for item in value:
            yield from numbers_below(item, path)
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        yield path, None, value


async def test_units_web_0_189_is_robot_0_1_and_the_web_never_sees_wire_values():
    async with rig() as r:
        async with web_connect(r.app) as web:
            await become_driver_and_arm(web, r.app)
            seq = 0
            seq, _ = await drive_for(web, seq, 1.2)
            # Robot side: every non-zero write is 0.189 / 1.89 = 0.1 (wire units).
            moving = nonzero_entries(r.stm)
            assert moving
            for entry in moving:
                assert entry[1] == pytest.approx(0.1) and entry[2] == 0.0 and entry[3] == 0.0
            # Web side: the robot's 0.1 comes back as 0.189, and the command in web units too.
            _, state = web.states[-1]
            assert state["vel"]["vx"] == pytest.approx(0.189, abs=0.003)
            assert state["cmd"]["vx"] == pytest.approx(0.189)
            assert state["last_cmd_seq"] in range(seq - 3, seq + 1)

            # Nothing received by the web may carry a wire value, the factor or its inverse.
            forbidden = (0.1, FACTOR, 1 / FACTOR)
            assert len(web.texts) >= 10
            for text in web.texts:
                for path, key, number in numbers_below(json.loads(text)):
                    if key is not None:
                        assert not any(w in key.lower() for w in ("wire", "divisor", "factor", "scale"))
                    elif path not in (("pose",), ("link",)):  # pose integrates, rtt_ms is a time
                        assert not any(math.isclose(number, f, rel_tol=1e-6) for f in forbidden), (
                            path,
                            number,
                        )
            # Binary scan frames: PROTO-2 shape, and no packed copy of those numbers.
            assert len(web.frames) >= 2
            for frame in web.frames:
                assert len(frame) == 734 and frame[0] == 2 and frame[1] == 1
                for number in forbidden:
                    for fmt in ("<d", "<f"):
                        assert struct.pack(fmt, number) not in frame


# ======================================================================================
# (b) SAF-02, SAF-03, SAF-07: disarmed by default, viewer, origin, tokens
# ======================================================================================


async def test_disarmed_by_default_viewer_cannot_drive_bad_origin_refused():
    async with rig() as r:
        await wait_link(r.app)
        for origin in ("http://evil.example", "http://localhost:3000", None):
            with pytest.raises(InvalidStatus) as refused:
                async with connect(r.app.ws_url, origin=origin):
                    pass
            assert refused.value.response.status_code == 403
        assert len(r.app.runtime.hub) == 0

        async with web_connect(r.app) as viewer:
            _, state = await viewer.wait_state(lambda s: True)
            assert state["session"]["armed"] is False  # SAF-02
            assert state["session"]["role"] == "viewer"
            # A viewer, and a client with the wrong operator token, cannot arm or drive.
            await viewer.send(t="arm", on=True)
            await viewer.send(t="hello", token="wrong-token")
            await viewer.send(t="arm", on=True)
            await viewer.send(t="cmd_vel", seq=1, vx=0.189, vy=0.0, wz=0.0, src="kbd")
            await asyncio.sleep(0.4)
            _, state = viewer.states[-1]
            assert state["session"]["armed"] is False and state["session"]["role"] == "viewer"
            assert nonzero_entries(r.stm) == []

            # The real operator: still disarmed until arm; a command while disarmed goes nowhere.
            await become_driver_and_arm(viewer, r.app, arm=False)
            _, state = viewer.states[-1]
            assert state["session"]["armed"] is False
            await viewer.send(t="cmd_vel", seq=2, vx=0.189, vy=0.0, wz=0.0, src="kbd")
            await asyncio.sleep(0.4)
            assert nonzero_entries(r.stm) == []
            since = len(viewer.states)
            await viewer.send(t="arm", on=True)
            await viewer.wait_state(lambda s: s["session"]["armed"], since=since)
            await viewer.send(t="cmd_vel", seq=3, vx=0.189, vy=0.0, wz=0.0, src="kbd")
            await wait_until(lambda: nonzero_entries(r.stm))


async def test_wrong_robot_token_is_refused_at_both_ends():
    async with rig(app_link_token="not-the-link-token") as r:
        # The app server presents a wrong token: the robot refuses, the link never comes up.
        await asyncio.sleep(0.6)
        assert r.app.runtime.link.connected is False
        async with web_connect(r.app) as web:
            await web.send(t="hello", token=OPERATOR_TOKEN)
            await web.send(t="arm", on=True)  # no arming while the robot link is down
            await asyncio.sleep(0.3)
            _, state = web.states[-1]
            assert state["link"]["robot"] is False and state["session"]["armed"] is False
        # A direct client with a wrong or missing token gets 401 and cannot move anything.
        for headers in ({"Authorization": "Bearer wrong"}, {}):
            with pytest.raises(InvalidStatus) as refused:
                async with connect(r.robot_url, additional_headers=headers):
                    pass
            assert refused.value.response.status_code == 401
        assert nonzero_entries(r.stm) == []


# ======================================================================================
# (c) NFR-02: command loop latency
# ======================================================================================


async def measure_loop(web, seq0, count):
    """cmd_vel sent -> first state whose last_cmd_seq equals that seq (as the client matches it)."""
    latencies = []
    for i in range(count):
        seq = seq0 + i + 1
        since = len(web.states)
        t0 = time.monotonic()
        await web.send(t="cmd_vel", seq=seq, vx=0.189, vy=0.0, wz=0.0, src="kbd")
        stamp, _ = await web.wait_state(lambda s, q=seq: s["last_cmd_seq"] == q, since=since)
        latencies.append(stamp - t0)
        # A varying gap (20 to 80 ms, always inside the 250 ms command timeout) so the samples are
        # not locked to the 20 Hz state tick.
        await asyncio.sleep(0.02 + 0.01 * ((i * 5) % 7))
    return latencies


async def test_command_loop_latency_p95_within_150_ms_over_60_commands():
    attempts = []
    async with rig() as r:
        async with web_connect(r.app) as web:
            await become_driver_and_arm(web, r.app)
            seq0 = 0
            for _ in range(3):  # a CPU spike may ruin one run; the bound must hold in one of three
                latencies = await measure_loop(web, seq0, 60)
                seq0 += 60
                assert len(latencies) == 60
                p95 = percentile(latencies, 0.95)
                attempts.append(p95)
                print(
                    "[e2e] command loop latency (60 cmds): p50 %.0f ms, p95 %.0f ms, max %.0f ms"
                    % (
                        statistics.median(latencies) * 1000,
                        p95 * 1000,
                        max(latencies) * 1000,
                    )
                )
                if p95 <= LOOP_P95_BOUND_S:
                    break
            # While the command was held the robot never saw a stray zero.
            assert_moving(r.stm)
    assert min(attempts) <= LOOP_P95_BOUND_S, attempts


# ======================================================================================
# (c) SAF-03 timings: zero reaches the STM32 simulator
# ======================================================================================


async def test_zero_after_the_operator_socket_drops():
    async with rig() as r:

        async def trial():
            async with web_connect(r.app) as web:
                await become_driver_and_arm(web, r.app)
                await drive_for(web, 0, 0.4)
                assert_moving(r.stm)
                t0 = time.monotonic()
                web.ws.transport.abort()  # the browser vanishes: no close frame
                latency = await zero_latency(r.stm, t0)
                await assert_stays_zero(r.stm, t0 + latency)
            await wait_until(
                lambda: not r.app.runtime.session.armed and r.app.runtime.session.driver is None
            )
            return latency

        await run_trials("operator socket drop -> zero", trial, STOP_BOUND_S)


async def test_zero_when_the_app_server_stops_sending_the_watchdog():
    # The robot-side deadman is set to 5 s so that only the app server watchdog can stop it.
    async with rig(deadman_s=5.0) as r:

        async def trial():
            async with web_connect(r.app) as web:
                await become_driver_and_arm(web, r.app)
                _, last_sent = await drive_for(web, 0, 0.4)
                assert_moving(r.stm)
                latency = await zero_latency(r.stm, last_sent)  # from the last command sent
                await assert_stays_zero(r.stm, last_sent + latency)
                assert r.app.runtime.session.armed is True  # still armed: only the command expired
                return latency

        await run_trials(
            "app watchdog (last cmd -> zero)", trial, SILENCE_BOUND_S, floor=0.8 * SILENCE_DEADLINE_S
        )


async def test_zero_and_no_resumption_when_the_robot_link_is_cut():
    async with rig() as r:

        async def trial():
            async with web_connect(r.app) as web:
                await become_driver_and_arm(web, r.app)
                seq, _ = await drive_for(web, 0, 0.4)
                assert_moving(r.stm)
                link = r.app.runtime.link
                assert link._ws is not None
                t0 = time.monotonic()
                link._ws.transport.abort()  # the cable is pulled: no close frame
                latency = await zero_latency(r.stm, t0)
                t_zero = t0 + latency
                # The operator keeps pressing the key during the outage and after recovery.
                since = len(web.states)
                seq, _ = await drive_for(web, seq, 0.5)
                await wait_until(lambda: link.connected)  # the link came back by itself
                seq, _ = await drive_for(web, seq, 0.5)
                # (d) Disarmed by the loss, so none of those commands ran and nothing old resumed
                # (the new link starts with a zero command).
                await assert_stays_zero(r.stm, t_zero, 0.1)
                _, state = web.states[-1]
                assert state["session"]["armed"] is False and state["link"]["robot"] is True
                assert any(not s["link"]["robot"] or not s["session"]["armed"] for _, s in web.states[since:])
            await wait_until(lambda: r.app.runtime.session.driver is None)
            return latency

        await run_trials("robot link cut -> zero", trial, STOP_BOUND_S)


async def test_zero_after_disarm():
    async with rig() as r:

        async def trial():
            async with web_connect(r.app) as web:
                await become_driver_and_arm(web, r.app)
                seq, _ = await drive_for(web, 0, 0.4)
                assert_moving(r.stm)
                t0 = time.monotonic()
                await web.send(t="arm", on=False)
                latency = await zero_latency(r.stm, t0)
                # Commands keep coming after the disarm; none may reach the robot.
                await drive_for(web, seq, 0.4)
                late = [e for e in list(r.stm.log) if e[0] > t0 + latency and not is_zero(e)]
                assert late == []
                _, state = web.states[-1]
                assert state["session"]["armed"] is False
                return latency

        await run_trials("disarm -> zero", trial, STOP_BOUND_S)


async def test_robot_deadman_stops_the_robot_when_the_app_server_is_killed_hard():
    # No app server: a bare client plays the app server. It sends commands, then goes silent with
    # the socket still open (a frozen or partitioned app server), so only the robot deadman acts.
    async with rig(with_app=False) as r:

        async def frozen_trial():
            async with bare_app_server(r.robot_url) as ws:
                last_sent = time.monotonic()
                for seq in range(1, 9):
                    last_sent = time.monotonic()
                    await ws.send(json.dumps({"t": "cmd_vel", "seq": seq, "vx": 0.1, "vy": 0.0, "wz": 0.0}))
                    await asyncio.sleep(0.05)
                assert_moving(r.stm)
                latency = await zero_latency(r.stm, last_sent)
                await assert_stays_zero(r.stm, last_sent + latency)
                return latency

        await run_trials(
            "robot deadman, sender frozen (last cmd -> zero)",
            frozen_trial,
            SILENCE_BOUND_S,
            floor=0.8 * SILENCE_DEADLINE_S,
        )

        async def killed_trial():
            async with bare_app_server(r.robot_url) as ws:
                for seq in range(1, 9):
                    await ws.send(json.dumps({"t": "cmd_vel", "seq": seq, "vx": 0.1, "vy": 0.0, "wz": 0.0}))
                    await asyncio.sleep(0.05)
                assert_moving(r.stm)
                t0 = time.monotonic()
                ws.transport.abort()  # kill -9: the kernel resets the connection
                latency = await zero_latency(r.stm, t0)
                await assert_stays_zero(r.stm, t0 + latency)
                return latency

        await run_trials("robot link lost, sender killed -> zero", killed_trial, STOP_BOUND_S)


# ======================================================================================
# (c) SAF-05: stop flag and stale telemetry force zero
# ======================================================================================


async def test_writer_forces_zero_on_stop_flag_and_stale_telemetry():
    async with rig() as r:
        async with web_connect(r.app) as web:
            await become_driver_and_arm(web, r.app)
            seq = 0
            for label, engage, release in (
                ("stop flag", lambda: setattr(r.stm, "flag_stop", 1), lambda: setattr(r.stm, "flag_stop", 0)),
                (
                    "stale telemetry",
                    lambda: setattr(r.stm, "telemetry_age_ns", 600_000_000),
                    lambda: setattr(r.stm, "telemetry_age_ns", 0),
                ),
            ):
                seq, _ = await drive_for(web, seq, 0.4)
                assert_moving(r.stm)
                t0 = time.monotonic()
                engage()
                latency = await zero_latency(r.stm, t0)
                print("[e2e] SAF-05 %s -> zero: %.0f ms (bound %.0f ms)" % (label, latency * 1000, FLAG_BOUND_S * 1000))
                assert latency <= FLAG_BOUND_S
                # Fresh commands keep arriving, yet the writer keeps writing zero while it lasts.
                seq, _ = await drive_for(web, seq, 0.5)
                late = [e for e in list(r.stm.log) if e[0] > t0 + latency and not is_zero(e)]
                assert late == [], label
                release()
                seq, _ = await drive_for(web, seq, 0.4)  # a new command moves it again
                assert_moving(r.stm)
            assert any(s["flag_stop"] == 0 for _, s in web.states)


# ======================================================================================
# (e) SAF-04: no clamping; int16 overflow is rejected and zero is written
# ======================================================================================


async def test_large_finite_values_are_sent_as_is_and_int16_overflow_is_rejected():
    async with rig() as r:
        async with web_connect(r.app) as web:
            await become_driver_and_arm(web, r.app)
            # 10 m/s on the web is 5.29 m/s on the wire: it fits the int16 frame, so it is not
            # clamped by the app server or the robot.
            since = len(web.states)
            await web.send(t="cmd_vel", seq=1, vx=10.0, vy=-10.0, wz=10.0, src="kbd")
            await web.wait_state(lambda s: s["last_cmd_seq"] == 1, since=since)
            await wait_until(lambda: nonzero_entries(r.stm))
            for entry in nonzero_entries(r.stm):
                assert entry[1] == pytest.approx(10.0 / FACTOR)
                assert entry[2] == pytest.approx(-10.0 / FACTOR)
                assert entry[3] == pytest.approx(10.0 / FACTOR)
            assert r.writer.health().rejected_count == 0

            # 70 m/s is 37.04 m/s on the wire, more than int16 millimetres can carry: rejected,
            # not clamped, and zero takes the place of the previous command.
            t0 = time.monotonic()
            await web.send(t="cmd_vel", seq=2, vx=70.0, vy=0.0, wz=0.0, src="kbd")
            latency = await zero_latency(r.stm, t0)
            print("[e2e] SAF-04 int16 overflow -> zero: %.0f ms" % (latency * 1000))
            assert latency <= FLAG_BOUND_S
            await wait_until(lambda: r.writer.health().rejected_count == 1)
            assert max(abs(e[1]) for e in list(r.stm.log)) < 6.0  # no clamped 32.767 anywhere

            # A huge finite value (the factor division stays finite) is rejected the same way.
            await web.send(t="cmd_vel", seq=3, vx=1e308, vy=0.0, wz=0.0, src="kbd")
            await wait_until(lambda: r.writer.health().rejected_count == 2)
            # NaN and Infinity literals never get past the app server.
            await web.send_raw('{"t":"cmd_vel","seq":4,"vx":NaN,"vy":0,"wz":0}')
            await web.send_raw('{"t":"cmd_vel","seq":5,"vx":Infinity,"vy":0,"wz":0}')
            await asyncio.sleep(0.3)
            assert r.writer.health().rejected_count == 2
            _, state = web.states[-1]
            # The NaN/Infinity commands (seq 4 and 5) never reached the robot. Seq 1 to 3 may show:
            # a zero command carries the newest seq the app server saw.
            assert state["last_cmd_seq"] < 4
            assert is_zero(r.stm.log[-1])

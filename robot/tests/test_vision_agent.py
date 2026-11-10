"""T19: vision agent skeleton - config, state machine (no GPU), PROTO-3 server, simulation."""
import asyncio
import json
import struct

import pytest
from websockets.asyncio.client import connect
from websockets.exceptions import InvalidStatus

from vision_agent import gesture_fsm as g
from vision_agent import pipeline as pl
from vision_agent.config import ConfigError, load_config
from vision_agent.gesture_fsm import NS, GestureFsm, Observation
from vision_agent.server import VisionServer, encode_frame

from test_robot import wait_for

TOKEN = "vision-test-token"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


# ------------------------------------------------------------------ config

def _env(**kw):
    return {"VISION_LINK_TOKEN": "t", "VISION_BIND_HOST": "100.69.39.18", **kw}


def test_config_requires_token_and_specific_host():
    with pytest.raises(ConfigError):
        load_config({})
    with pytest.raises(ConfigError):
        load_config(_env(VISION_BIND_HOST="0.0.0.0"))
    with pytest.raises(ConfigError):
        load_config(_env(VISION_BIND_PORT="x"))
    with pytest.raises(ConfigError):
        load_config(_env(VISION_BIND_PORT="70000"))
    with pytest.raises(ConfigError):
        load_config(_env(VISION_SIMULATE="maybe"))


def test_config_defaults():
    c = load_config(_env())
    assert (c.simulate, c.bind_port) == (False, 8766)
    assert load_config(_env(VISION_SIMULATE="true")).simulate


# ------------------------------------------------------------------ FSM

def _on(now=0):
    f = GestureFsm()
    f.mode_changed(True, now)
    return f


def _obs(**kw):
    return Observation(**kw)


def test_off_ignores_everything_and_mode_on_locks():
    f = GestureFsm()
    assert f.step(_obs(face_match=True, track_id=1), NS) == "OFF"
    f.mode_changed(True, NS)
    assert f.state == "LOCKED"


def test_happy_path_to_follow_and_back():
    f = _on()
    t = [0]

    def go(obs, dt=0.1):
        t[0] += int(dt * NS)
        return f.step(obs, t[0], user="u1")

    assert go(_obs(face_match=True, track_id=7)) == "BIND"
    assert f.user == "u1"
    assert go(_obs(track_id=7, in_gesture_zone=True, bound_visible=True)) == "GESTURE"
    assert go(_obs(track_id=7, bound_visible=True, open_palm_1s=True)) == "BIND-BACK"
    assert go(_obs(track_id=7, bound_visible=True, back_gallery_full=True)) == "FOLLOW"
    assert go(_obs(track_id=7, bound_visible=True, exit_gesture=True)) == "GESTURE"


def test_command_is_zero_in_every_state():
    assert GestureFsm().command() == (0.0, 0.0, 0.0)


def test_bind_times_out_on_id_change_or_other_person():
    for bad in (_obs(track_id=9), _obs(track_id=7, other_person_near=True)):
        f = _on()
        f.step(_obs(face_match=True, track_id=7), 1)
        assert f.step(bad, 2) == "LOCKED"
    f = _on()
    f.step(_obs(face_match=True, track_id=7), 1)
    assert f.step(_obs(track_id=7), int(8.1 * NS)) == "LOCKED"


def test_bind_back_timeout_returns_to_gesture():
    f = _on()
    f.step(_obs(face_match=True, track_id=1), 1)
    f.step(_obs(track_id=1, in_gesture_zone=True, bound_visible=True), 2)
    f.step(_obs(track_id=1, bound_visible=True, open_palm_1s=True), 3)
    assert f.state == "BIND-BACK"
    assert f.step(_obs(track_id=1, bound_visible=True), int(10.1 * NS)) == "GESTURE"


def _to_gesture():
    f = _on()
    f.step(_obs(face_match=True, track_id=1), 1)
    f.step(_obs(track_id=1, in_gesture_zone=True, bound_visible=True), 2)
    assert f.state == "GESTURE"
    return f


def test_gesture_lost_over_3s_goes_hold_then_recovers_or_locks():
    f = _to_gesture()
    f.step(_obs(track_id=1), 10)
    assert f.step(_obs(track_id=1), 10 + int(2.9 * NS)) == "GESTURE"
    assert f.step(_obs(track_id=1), 10 + int(3.1 * NS)) == "HOLD"
    t = 10 + int(3.2 * NS)
    assert f.step(_obs(reacquired=True), t) == "GESTURE"
    f = _to_gesture()
    f.step(_obs(), 10)
    f.step(_obs(), 10 + int(3.1 * NS))
    assert f.state == "HOLD"
    assert f.step(_obs(), 10 + int(3.1 * NS) + int(12.1 * NS)) == "LOCKED"


def test_follow_lost_goes_hold_and_returns_to_follow():
    f = _to_gesture()
    f.step(_obs(track_id=1, bound_visible=True, open_palm_1s=True), 3)
    f.step(_obs(track_id=1, bound_visible=True, back_gallery_full=True), 4)
    assert f.state == "FOLLOW"
    f.step(_obs(track_id=1, bound_visible=False), 100)
    assert f.step(_obs(track_id=1, bound_visible=False), 100 + int(1.6 * NS)) == "HOLD"
    assert f.step(_obs(reacquired=True), 100 + int(1.7 * NS)) == "FOLLOW"


def test_follow_identity_low_goes_hold():
    f = _to_gesture()
    f.step(_obs(track_id=1, bound_visible=True, open_palm_1s=True), 3)
    f.step(_obs(track_id=1, bound_visible=True, back_gallery_full=True), 4)
    assert f.step(_obs(track_id=1, bound_visible=True, identity_low=True), 5) == "HOLD"


def test_estop_on_status_loss_flag_stop_or_camera_and_clears_after_calm():
    for kw, ob in (({"status_age_s": 0.6}, _obs()), ({"flag_stop": True}, _obs()),
                   ({}, _obs(camera_error=True))):
        f = _to_gesture()
        assert f.step(ob, 10, **kw) == "ESTOP"
    f = _to_gesture()
    f.step(_obs(), 10, flag_stop=True)
    assert f.step(_obs(), 11, flag_stop=True) == "ESTOP"  # fault still present
    assert f.step(_obs(), 20, robot_still=False) == "ESTOP"
    f.step(_obs(), 30)
    assert f.step(_obs(), 30 + int(1.9 * NS)) == "ESTOP"
    assert f.step(_obs(), 30 + int(2.1 * NS)) == "LOCKED"


def test_user_disabled_and_session_expiry_lock():
    f = _to_gesture()
    assert f.step(_obs(user_disabled=True), 10) == "LOCKED" and f.user is None
    f = _to_gesture()
    assert f.step(_obs(), int((g.SESSION_S + 1) * NS)) == "LOCKED"


def test_mode_off_returns_to_off_from_anywhere():
    f = _to_gesture()
    f.mode_changed(False, 20)
    assert f.state == "OFF" and f.user is None


def test_enroll_only_from_off():
    f = GestureFsm()
    assert f.enroll(True, 1) and f.state == "ENROLL"
    assert not f.enroll(True, 2)
    assert f.enroll(False, 3) and f.state == "OFF"
    f = _on()
    assert not f.enroll(True, 1)


# ------------------------------------------------------------------ simulation

def test_sim_script_walks_the_states_and_stays_zero():
    p = pl.Pipeline(simulate=True)
    p.mode_changed(True, 0)
    seen = []
    for step in range(0, 140):
        now = step * NS // 10
        p.frame(now)
        assert p.fsm.command() == (0.0, 0.0, 0.0)
        if not seen or seen[-1] != p.fsm.state:
            seen.append(p.fsm.state)
    assert seen[:5] == ["LOCKED", "BIND", "GESTURE", "BIND-BACK", "FOLLOW"]
    assert "HOLD" in seen


def test_sim_frame_is_a_jpeg_and_state_has_no_velocity():
    p = pl.Pipeline(simulate=True)
    assert p.frame(1)[:2] == b"\xff\xd8"
    state = p.vision_state(False)
    assert state["t"] == "vision_state" and state["state"] == "OFF"
    assert not {"vx", "vy", "wz"} & set(state) and "vx" not in state["cmd"]


def test_idle_pipeline_without_simulation_observes_nothing():
    p = pl.Pipeline(simulate=False)
    p.mode_changed(True, 0)
    p.frame(NS)
    assert p.fsm.state == "LOCKED"


# ------------------------------------------------------------------ PROTO-3 server

def test_encode_frame_layout():
    data = encode_frame(5, 1234, b"JPG")
    assert struct.unpack("<BBIQ", data[:14]) == (3, 1, 5, 1234) and data[14:] == b"JPG"


async def _server(on_command=None):
    srv = VisionServer(token=TOKEN, get_state=lambda: {"t": "vision_state", "state": "OFF"},
                       on_command=on_command)
    port = await srv.start("127.0.0.1", 0)
    return srv, f"ws://127.0.0.1:{port}/ws"


async def test_server_refuses_bad_token_and_path():
    srv, url = await _server()
    try:
        for headers in ({}, {"Authorization": "Bearer nope"}, {"Authorization": TOKEN}):
            with pytest.raises(InvalidStatus) as e:
                async with connect(url, additional_headers=headers):
                    pass
            assert e.value.response.status_code == 401
        with pytest.raises(InvalidStatus) as e:
            async with connect(url.replace("/ws", "/x"), additional_headers=AUTH):
                pass
        assert e.value.response.status_code == 404
    finally:
        await srv.close()


async def test_server_streams_state_and_newest_frame():
    srv, url = await _server()
    try:
        async with connect(url, additional_headers=AUTH) as ws:
            first = json.loads(await asyncio.wait_for(ws.recv(), 2))
            assert first["t"] == "vision_state"
            srv.publish_frame(1, 10, b"A")
            srv.publish_frame(2, 20, b"B")  # replaces the unsent frame
            while True:
                msg = await asyncio.wait_for(ws.recv(), 2)
                if isinstance(msg, bytes):
                    break
            assert struct.unpack("<BBIQ", msg[:14])[2] == 2 and msg[14:] == b"B"
    finally:
        await srv.close()


async def test_server_commands_are_dispatched_and_unknown_or_velocity_ignored():
    got = []

    def on_command(data):
        got.append(data["t"])
        return {"count": 0}

    srv, url = await _server(on_command)
    try:
        async with connect(url, additional_headers=AUTH) as ws:
            await ws.send(json.dumps({"t": "cmd_vel", "seq": 1, "vx": 1, "vy": 0, "wz": 0}))
            await ws.send("not json")
            await ws.send(json.dumps({"t": "staff_list"}))
            while True:
                msg = json.loads(await asyncio.wait_for(ws.recv(), 2))
                if msg.get("t") == "result":
                    break
            assert msg == {"t": "result", "of": "staff_list", "ok": True, "count": 0}
            assert got == ["staff_list"]
    finally:
        await srv.close()


def test_server_rejects_empty_token():
    with pytest.raises(ValueError):
        VisionServer(token="", get_state=dict)


async def test_robot_link_roundtrip_is_skipped_on_windows_but_class_imports():
    from vision_agent.__main__ import RobotLink

    link = RobotLink("/nonexistent", "/nonexistent2")
    link.send_cmd(1, "OFF", None, (0, 0, 0))  # no socket: silently does nothing
    link.poll(1)
    assert link.status_ns is None

"""T18: gesture mode on the robot agent - ModeGuard, LidarGate, CmdArbiter, PROTO-2 mode/hb, PROTO-4."""
import asyncio
import json
import math
import socket
import sys
from types import SimpleNamespace

import pytest

from robot_agent import drive, local_link, server, sim
from robot_agent.drive import CmdArbiter, LidarGate, ModeGuard
from robot_agent.hardware import LidarPoint, LidarScan

from test_robot import AUTH, TOKEN, FakeWriter, _cmd, _devices_ok, wait_for
from websockets.asyncio.client import connect

NS = 1_000_000_000
T0 = 10 * NS


def _scan(points, t_ns=T0):
    return LidarScan(t_ns=t_ns, points=tuple(LidarPoint(t_ns, a, r, 0, 0) for a, r in points))


class Lidar:
    def __init__(self, scan=None):
        self.latest = scan


def _arbiter(scan=None, enabled=True, **kw):
    writer = FakeWriter()
    lidar = Lidar(scan if scan is not None else _scan([]))
    arb = CmdArbiter(writer, lidar=lidar, vision_enabled=enabled, **kw)
    return arb, writer, lidar


def _run(arb, seq, vx=0.1, vy=0.0, wz=0.0, state="GESTURE", t=T0):
    assert arb.submit_vision(seq, t, vx, vy, wz, state)
    return arb.step(t)


# ------------------------------------------------------------------ ModeGuard

def test_mode_guard_thresholds():
    g = ModeGuard()
    assert not g.blocked(T0) and not g.update(T0)
    g.enable(T0)
    assert g.on and not g.blocked(T0 + 500_000_000)
    assert g.blocked(T0 + 500_000_001)
    assert not g.update(T0 + 3 * NS)
    assert g.update(T0 + 3 * NS + 1)
    assert not g.on and g.reason == "heartbeat"


def test_heartbeat_resets_both_timers():
    g = ModeGuard()
    g.enable(T0)
    g.heartbeat(T0 + 2 * NS)
    assert not g.blocked(T0 + 2 * NS + 400_000_000)
    assert not g.update(T0 + 4 * NS)


# ------------------------------------------------------------------ LidarGate

def test_gate_zero_always_passes_even_without_scan():
    assert LidarGate().check(0, 0, 0, None, T0) == (False, None)


def test_gate_blocks_without_or_with_stale_scan():
    g = LidarGate()
    assert g.check(0.1, 0, 0, None, T0)[0]
    assert g.check(0.1, 0, 0, _scan([], T0 - 301_000_000), T0)[0]
    assert not g.check(0.1, 0, 0, _scan([], T0 - 299_000_000), T0)[0]
    assert g.check(0.1, 0, 0, _scan([], T0 + 1), T0)[0]  # scan from the future


def test_gate_nan_command_is_blocked():
    assert LidarGate().check(float("nan"), 0, 0, _scan([]), T0)[0]


def test_gate_obstacle_ahead_blocks_and_behind_does_not():
    g = LidarGate()
    ahead = _scan([(0.0, 0.5)])  # 0.5 m ahead of the LiDAR = 0.6 m from the centre
    behind = _scan([(math.pi, 0.5)])
    assert g.check(0.5, 0, 0, ahead, T0) == (True, 0.5)
    assert not g.check(0.5, 0, 0, behind, T0)[0]
    assert g.check(-0.5, 0, 0, behind, T0)[0]


def test_gate_is_asymmetric_because_lidar_is_ahead_of_centre():
    g = LidarGate()
    # Stationary-ish probe: tiny vx so the swept area is the footprint plus the margin.
    # Centre-frame limit ahead = 0.20 + 0.15 = 0.35; the LiDAR range for that is 0.25.
    assert g.check(0.01, 0, 0, _scan([(0.0, 0.24)]), T0)[0]
    assert not g.check(0.01, 0, 0, _scan([(0.0, 0.27)]), T0)[0]
    # Behind: x_r = -r + 0.10, blocked when r <= 0.45.
    assert g.check(-0.01, 0, 0, _scan([(math.pi, 0.44)]), T0)[0]
    assert not g.check(-0.01, 0, 0, _scan([(math.pi, 0.47)]), T0)[0]


def test_gate_swept_area_grows_with_speed():
    g = LidarGate()
    far = _scan([(0.0, 1.0)])  # 1.1 m from the centre
    assert not g.check(0.3, 0, 0, far, T0)[0]  # reaches 0.15 m in 0.5 s
    assert g.check(2.0, 0, 0, far, T0)[0]  # reaches 1.0 m


def test_gate_rotation_sweeps_the_corners():
    g = LidarGate()
    # Point just outside the static box + margin on the side, caught only when rotating.
    side = _scan([(math.pi / 2, 0.40)])  # y = 0.40, x = 0.10
    assert not g.check(0.0, 0.0, 0.001, side, T0)[0]
    assert g.check(0.0, 0.0, 3.0, side, T0)[0]


def test_gate_ignores_invalid_points():
    g = LidarGate()
    scan = _scan([(0.0, 0.0), (0.0, float("nan")), (float("inf"), 0.3), (0.0, -1.0)])
    assert not g.check(0.5, 0, 0, scan, T0)[0]


def test_gate_self_check_counts_points_in_footprint():
    g = LidarGate()
    assert g.self_check(_scan([(0.0, 0.05), (0.0, 2.0)])) == 1


# ------------------------------------------------------------------ CmdArbiter

def test_vision_is_ignored_when_mode_is_off():
    arb, w, _ = _arbiter()
    assert not arb.submit_vision(1, T0, 0.1, 0, 0, "GESTURE")
    assert arb.step(T0) is None and w.calls == []


def test_vision_forwarded_when_mode_on():
    arb, w, _ = _arbiter()
    arb.set_mode(True, now_ns=T0)
    assert _run(arb, 1, vx=0.1) == (0.1, 0.0, 0.0)
    assert w.calls == [(0.1, 0.0, 0.0)]
    assert arb.report(T0)["src"] == "vision"


def test_vision_motion_flag_off_never_forwards():
    arb, w, _ = _arbiter(enabled=False)
    arb.set_mode(True, now_ns=T0)
    assert _run(arb, 1) is None and w.calls == []


@pytest.mark.parametrize("state", ["OFF", "LOCKED", "BIND", "ESTOP", "bogus"])
def test_only_run_states_are_forwarded(state):
    arb, w, _ = _arbiter()
    arb.set_mode(True, now_ns=T0)
    assert _run(arb, 1, state=state) is None and w.calls == []


@pytest.mark.parametrize("state", ["GESTURE", "FOLLOW", "HOLD"])
def test_run_states_are_forwarded(state):
    arb, w, _ = _arbiter()
    arb.set_mode(True, now_ns=T0)
    assert _run(arb, 1, state=state) is not None


def test_stale_vision_command_is_not_forwarded():
    arb, w, _ = _arbiter()
    arb.set_mode(True, now_ns=T0)
    arb.submit_vision(1, T0, 0.1, 0, 0, "GESTURE")
    assert arb.step(T0 + 101_000_000) is None
    assert arb.step(T0 - 1) is None  # timestamp from the future


def test_vision_seq_must_increase():
    arb, w, _ = _arbiter()
    arb.set_mode(True, now_ns=T0)
    assert arb.submit_vision(5, T0, 0.1, 0, 0, "GESTURE")
    assert not arb.submit_vision(5, T0, 0.2, 0, 0, "GESTURE")
    assert not arb.submit_vision(4, T0, 0.2, 0, 0, "GESTURE")
    assert arb.step(T0) == (0.1, 0.0, 0.0)


def test_heartbeat_over_half_second_blocks_vision_and_zeroes():
    arb, w, _ = _arbiter()
    arb.set_mode(True, now_ns=T0)
    _run(arb, 1)
    clears = w.clears
    arb.submit_vision(2, T0 + 600_000_000, 0.1, 0, 0, "GESTURE")
    assert arb.step(T0 + 600_000_000) is None
    assert w.clears == clears + 1  # was driving from vision, zeroed at once
    assert arb.guard.on
    assert arb.report(T0 + 600_000_000)["vision"]["blocked"]


def test_heartbeat_recovery_resumes_vision():
    arb, w, _ = _arbiter()
    arb.set_mode(True, now_ns=T0)
    arb._lidar.latest = _scan([], T0 + 600_000_000)
    arb.heartbeat(T0 + 600_000_000)
    arb.submit_vision(1, T0 + 600_000_000, 0.1, 0, 0, "GESTURE")
    assert arb.step(T0 + 600_000_000) == (0.1, 0.0, 0.0)


def test_heartbeat_over_three_seconds_turns_mode_off():
    arb, w, _ = _arbiter()
    arb.set_mode(True, now_ns=T0)
    _run(arb, 1)
    arb.step(T0 + 3 * NS + 1)
    assert not arb.guard.on and arb.guard.reason == "heartbeat"
    assert w.clears >= 1
    assert arb.report()["mode"] == "manual"


def test_manual_nonzero_wins_and_turns_mode_off():
    arb, w, _ = _arbiter()
    arb.set_mode(True, now_ns=T0)
    _run(arb, 1)
    assert arb.set_cmd_vel(0.0, 0.2, 0.0, T0)
    assert not arb.guard.on and arb.guard.reason == "manual"
    assert w.calls[-1] == (0.0, 0.2, 0.0)
    assert arb.step(T0) is None


def test_manual_zero_is_ignored_while_mode_is_on():
    arb, w, _ = _arbiter()
    arb.set_mode(True, now_ns=T0)
    _run(arb, 1)
    before = list(w.calls)
    assert arb.set_cmd_vel(0.0, 0.0, 0.0, T0)
    assert arb.guard.on and w.calls == before


def test_manual_works_normally_when_mode_is_off():
    arb, w, _ = _arbiter()
    arb.set_cmd_vel(0.0, 0.0, 0.0, T0)
    arb.set_cmd_vel(0.1, 0.0, 0.0, T0)
    assert w.calls == [(0.0, 0.0, 0.0), (0.1, 0.0, 0.0)]


def test_manual_nan_reaches_writer_to_be_rejected():
    arb, w, _ = _arbiter()
    arb.set_mode(True, now_ns=T0)
    arb.set_cmd_vel(float("nan"), 0.0, 0.0, T0)
    assert not arb.guard.on  # non-zero intent: manual takes over, writer decides


def test_link_loss_clears_mode_and_writer():
    arb, w, _ = _arbiter()
    arb.set_mode(True, now_ns=T0)
    arb.clear()
    assert not arb.guard.on and arb.guard.reason == "link" and w.clears >= 1


def test_mode_off_clears_writer_only_if_it_was_on():
    arb, w, _ = _arbiter()
    arb.set_mode(False)
    assert w.clears == 0
    arb.set_mode(True, now_ns=T0)
    arb.set_mode(False)
    assert w.clears == 1


def test_gate_blocks_vision_to_zero_but_does_not_clamp():
    arb, w, _ = _arbiter(scan=_scan([(0.0, 0.3)]))
    arb.set_mode(True, now_ns=T0)
    assert _run(arb, 1, vx=0.3) == (0.0, 0.0, 0.0)
    assert w.calls[-1] == (0.0, 0.0, 0.0)
    rep = arb.report(T0)
    assert rep["lidar_gate"]["blocked"] and rep["lidar_gate"]["min_m"] == 0.3


def test_gate_passes_full_speed_when_clear():
    arb, w, _ = _arbiter(scan=_scan([(0.0, 3.0)]))
    arb.set_mode(True, now_ns=T0)
    assert _run(arb, 1, vx=0.5) == (0.5, 0.0, 0.0)  # not clamped


def test_gate_does_not_apply_to_manual_commands():
    arb, w, _ = _arbiter(scan=_scan([(0.0, 0.3)]))
    arb.set_cmd_vel(0.3, 0, 0, T0)
    assert w.calls == [(0.3, 0, 0)]


def test_no_lidar_blocks_vision():
    arb = CmdArbiter(FakeWriter(), lidar=None, vision_enabled=True)
    arb.set_mode(True, now_ns=T0)
    arb.submit_vision(1, T0, 0.1, 0, 0, "GESTURE")
    assert arb.step(T0) == (0.0, 0.0, 0.0)


def test_robot_status_payload():
    arb, _, _ = _arbiter()
    arb.set_mode(True, now_ns=T0)
    stm = SimpleNamespace(flag_stop=0, gyro_z_radps=0.25)
    st = arb.robot_status(stm, T0 + 100)
    assert st == {
        "t": "robot_status", "t_mono_ns": T0 + 100, "mode": True, "blocked": False,
        "flag_stop": False, "gz": 0.25, "lidar_ok": True,
    }
    none = arb.robot_status(None, T0 + 100)
    assert none["flag_stop"] is True and none["gz"] == 0.0


def test_robot_status_lidar_not_ok_when_stale():
    arb, _, _ = _arbiter()
    assert not arb.robot_status(None, T0 + NS)["lidar_ok"]


# ------------------------------------------------------------------ PROTO-4 parsing

def _vc(**over):
    base = {"t": "vision_cmd", "seq": 1, "t_mono_ns": T0, "vx": 0.1, "vy": 0, "wz": -0.2,
            "state": "GESTURE", "user": "u1"}
    base.update(over)
    return base


def test_parse_vision_cmd_ok():
    assert local_link.parse_vision_cmd(_vc()) == (1, T0, 0.1, 0.0, -0.2, "GESTURE")
    assert local_link.parse_vision_cmd(_vc(user=None)) is not None


@pytest.mark.parametrize("bad", [
    _vc(vx=float("nan")), _vc(vy=float("inf")), _vc(vx="1"), _vc(vx=True), _vc(seq=1.5),
    _vc(seq=True), _vc(t_mono_ns="1"), _vc(state=3), _vc(user=[]), _vc(t="cmd_vel"),
    {k: v for k, v in _vc().items() if k != "wz"}, {**_vc(), "extra": 1}, [], "x", None,
])
def test_parse_vision_cmd_rejects(bad):
    assert local_link.parse_vision_cmd(bad) is None


def test_on_datagram_feeds_arbiter_and_counts_drops():
    arb, w, _ = _arbiter()
    arb.set_mode(True, now_ns=T0)
    link = local_link.VisionLink(arb, SimpleNamespace(latest=None), "/unused")
    link.on_datagram(json.dumps(_vc()).encode(), "peer")
    assert arb._vision is not None and link._peer == "peer"
    for junk in (b"\xff\xfe", b"{", b"[]", b"x" * 2000, b'{"t":"vision_cmd"}'):
        link.on_datagram(junk, None)
    assert link.dropped == 5


def test_send_status_needs_peer_and_survives_send_errors():
    arb, _, _ = _arbiter()
    link = local_link.VisionLink(arb, SimpleNamespace(latest=None), "/unused")
    assert not link.send_status()
    sent = []

    class T:
        def sendto(self, data, addr):
            if addr == "gone":
                raise OSError("no peer")
            sent.append((json.loads(data), addr))

        def close(self):
            pass

    link._transport = T()
    link._peer = "gone"
    assert not link.send_status()
    link._peer = "vis"
    assert link.send_status()
    assert sent[0][0]["t"] == "robot_status" and sent[0][1] == "vis"


async def test_arbiter_loop_survives_exceptions():
    calls = []

    class Arb:
        def step(self):
            calls.append(1)
            if len(calls) == 1:
                raise RuntimeError("boom")

    task = asyncio.ensure_future(local_link.arbiter_loop(Arb(), period_s=0.005))
    await wait_for(lambda: len(calls) >= 3)
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)


@pytest.mark.skipif(not hasattr(socket, "AF_UNIX") or sys.platform == "win32",
                    reason="unix datagram sockets are Jetson/Linux only")
async def test_unix_socket_roundtrip(tmp_path):
    arb, _, _ = _arbiter()
    arb.set_mode(True, now_ns=0)
    path = str(tmp_path / "vision.sock")
    link = local_link.VisionLink(arb, SimpleNamespace(latest=None), path)
    await link.start()
    client_path = str(tmp_path / "client.sock")
    client = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    client.bind(client_path)
    client.setblocking(False)
    try:
        client.sendto(json.dumps(_vc()).encode(), path)
        await wait_for(lambda: arb._vision is not None)
        await wait_for(lambda: link._peer is not None)
        assert link.send_status()
        loop = asyncio.get_running_loop()
        data = await asyncio.wait_for(loop.sock_recv(client, 2048), 2)
        assert json.loads(data)["t"] == "robot_status"
    finally:
        client.close()
        link.stop()


# ------------------------------------------------------------------ PROTO-2 mode / hb via server

async def _rig_with_arbiter():
    writer = FakeWriter()
    arb = CmdArbiter(writer, lidar=Lidar(_scan([])), vision_enabled=True)
    stm = sim.SimulatedStm32()
    stm.start()
    srv = server.RobotServer(
        token=TOKEN, writer=writer, stm=stm, devices=_devices_ok, arbiter=arb
    )
    port = await srv.start("127.0.0.1", 0)
    return srv, arb, writer, stm, f"ws://127.0.0.1:{port}/ws"


async def test_server_mode_hb_and_state_report():
    srv, arb, writer, stm, url = await _rig_with_arbiter()
    try:
        async with connect(url, additional_headers=AUTH) as ws:
            await ws.send(json.dumps({"t": "mode", "seq": 1, "gesture": True}))
            await wait_for(lambda: arb.guard.on)
            await ws.send(json.dumps({"t": "hb", "seq": 1}))
            await ws.send(json.dumps({"t": "hb", "seq": 1}))  # repeated: ignored
            await ws.send(json.dumps({"t": "mode", "seq": 1, "gesture": False}))  # old seq
            await ws.send(json.dumps({"t": "mode", "seq": 2, "gesture": "yes"}))  # bad type
            await asyncio.sleep(0.1)
            assert arb.guard.on
            state = None
            for _ in range(40):
                msg = json.loads(await asyncio.wait_for(ws.recv(), 2))
                if msg.get("t") == "state":
                    state = msg
                    if state.get("mode") == "gesture":
                        break
            assert state["mode"] == "gesture" and "lidar_gate" in state and "vision" in state
            await ws.send(json.dumps({"t": "mode", "seq": 3, "gesture": False}))
            await wait_for(lambda: not arb.guard.on)
        assert writer.clears >= 1  # disconnect clears too
    finally:
        await srv.close()
        stm.stop()


async def test_server_manual_cmd_vel_turns_mode_off_and_new_link_starts_manual():
    srv, arb, writer, stm, url = await _rig_with_arbiter()
    try:
        async with connect(url, additional_headers=AUTH) as ws:
            await ws.send(json.dumps({"t": "mode", "seq": 1, "gesture": True}))
            await wait_for(lambda: arb.guard.on)
            await ws.send(_cmd(seq=1, vx=0.0, vy=0.0, wz=0.0))
            await asyncio.sleep(0.1)
            assert arb.guard.on  # zero ignored
            await ws.send(_cmd(seq=2, vx=0.2, vy=0.0, wz=0.0))
            await wait_for(lambda: not arb.guard.on)
            assert writer.calls[-1] == (0.2, 0.0, 0.0)
            await ws.send(json.dumps({"t": "mode", "seq": 2, "gesture": True}))
            await wait_for(lambda: arb.guard.on)
        await wait_for(lambda: not arb.guard.on)  # link lost
        async with connect(url, additional_headers=AUTH):
            assert not arb.guard.on
    finally:
        await srv.close()
        stm.stop()


def test_parse_session():
    assert server.parse_session({"t": "mode", "seq": 1, "gesture": True}) == ("mode", 1, True)
    assert server.parse_session({"t": "hb", "seq": 4}) == ("hb", 4, False)
    for bad in ({"t": "mode", "seq": 1}, {"t": "hb", "seq": True}, {"t": "hb", "seq": 1, "v": 1},
                {"t": "mode", "seq": 1, "gesture": 1}, {"t": "x"}, [], None):
        assert server.parse_session(bad) is None


def test_run_states_constant():
    assert drive.VISION_RUN_STATES == {"GESTURE", "FOLLOW", "HOLD"}

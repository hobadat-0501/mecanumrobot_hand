import asyncio
import json
import math
import struct
import time
from contextlib import asynccontextmanager
from http import HTTPStatus
from types import SimpleNamespace

import httpx
import pytest
import uvicorn
from websockets.asyncio.client import connect
from websockets.asyncio.server import serve
from websockets.exceptions import ConnectionClosed, InvalidStatus
from websockets.protocol import State

from app_server import control
from app_server import main as app_main
from app_server import telemetry as telemetry_module
from app_server.config import ConfigError, load_settings
from app_server.control import (
    CMD_VEL_DIVISOR,
    ControlSession,
    origin_allowed,
    to_wire_units,
    token_matches,
    validate_cmd_vel,
)
from app_server.main import Hub, create_app
from app_server.robot_link import RobotLink
from app_server.telemetry import Odometry, Telemetry

ORIGIN = "http://100.119.83.63:3000"


class FakeClock:
    def __init__(self):
        self.t = 100.0

    def __call__(self):
        return self.t


def make_session(clock=None):
    return ControlSession("secret", [ORIGIN], clock or FakeClock())


def driver_session(clock=None):
    s = make_session(clock)
    assert s.connect("a", ORIGIN)
    assert s.hello("a", "secret")
    return s


def cmd(seq=1, vx=0.0, vy=0.0, wz=0.0):
    return {"type": "cmd_vel", "seq": seq, "vx": vx, "vy": vy, "wz": wz, "src": "kbd"}


def test_package_imports():
    import app_server

    assert app_server is not None


# ---- config ----

BASE_ENV = {"ROBOT_LINK_TOKEN": "link", "OPERATOR_TOKEN": "op"}


def test_config_defaults_and_frozen():
    s = load_settings(dict(BASE_ENV))
    assert s.robot_ws_url == "ws://100.69.39.18:8765/ws"
    assert s.bind_host == "100.119.83.63"
    assert s.bind_port == 8000
    assert s.allowed_origins == (ORIGIN,)
    with pytest.raises(Exception):
        s.bind_port = 1


def test_config_parses_origins_and_port():
    env = dict(BASE_ENV, APP_ALLOWED_ORIGINS=" http://a:1 , http://b:2 ,", APP_BIND_PORT="9000")
    s = load_settings(env)
    assert s.allowed_origins == ("http://a:1", "http://b:2")
    assert s.bind_port == 9000


@pytest.mark.parametrize("missing", ["ROBOT_LINK_TOKEN", "OPERATOR_TOKEN"])
@pytest.mark.parametrize("value", [None, "", "   "])
def test_config_empty_token_refuses_to_start(missing, value):
    env = dict(BASE_ENV)
    if value is None:
        del env[missing]
    else:
        env[missing] = value
    with pytest.raises(ConfigError):
        load_settings(env)


def test_config_bad_port():
    with pytest.raises(ConfigError):
        load_settings(dict(BASE_ENV, APP_BIND_PORT="abc"))


def test_config_has_no_divisor_setting():
    s = load_settings(dict(BASE_ENV, CMD_VEL_DIVISOR="5"))
    assert not any("divisor" in f.lower() for f in s.__dataclass_fields__)
    assert CMD_VEL_DIVISOR == 1.89


# ---- disarm by default, arm rights ----

def test_starts_disarmed():
    s = make_session()
    assert s.armed is False
    assert s.snapshot()["armed"] is False


def test_disarmed_driver_command_not_forwarded():
    s = driver_session()
    assert s.handle_cmd_vel("a", cmd(vx=1.0)) is None


def test_arm_then_forward():
    s = driver_session()
    assert s.arm("a", True) is True
    assert s.armed is True
    assert s.handle_cmd_vel("a", cmd(vx=1.0)) is not None


def test_disarm_stops_forwarding():
    s = driver_session()
    s.arm("a", True)
    assert s.arm("a", False) is True
    assert s.armed is False
    assert s.handle_cmd_vel("a", cmd(vx=1.0)) is None
    assert s.snapshot()["cmd"] == {"vx": 0.0, "vy": 0.0, "wz": 0.0}


def test_arm_requires_bool_and_driver():
    s = driver_session()
    assert s.arm("a", "yes") is False
    assert s.armed is False
    assert s.connect("v", ORIGIN)
    assert s.arm("v", True) is False
    assert s.armed is False


# ---- 1.89 division, single function ----

def test_divisor_constant():
    assert CMD_VEL_DIVISOR == 1.89


def test_to_wire_units_divides_all_three():
    vx, vy, wz = to_wire_units(1.89, -3.78, 0.189)
    assert vx == pytest.approx(1.0)
    assert vy == pytest.approx(-2.0)
    assert wz == pytest.approx(0.1)


def test_to_wire_units_known_vector():
    vx, vy, wz = to_wire_units(0.1, 0.1, 0.1)
    for v in (vx, vy, wz):
        assert v == pytest.approx(0.1 / 1.89)
    assert round(vx * 1000) == 53  # 52.91 mm/s


def test_handle_cmd_vel_output_is_wire_only():
    s = driver_session()
    s.arm("a", True)
    out = s.handle_cmd_vel("a", cmd(seq=7, vx=1.89, vy=3.78, wz=-0.945))
    assert set(out) == {"seq", "vx", "vy", "wz"}
    assert out["seq"] == 7
    assert out["vx"] == pytest.approx(1.0)
    assert out["vy"] == pytest.approx(2.0)
    assert out["wz"] == pytest.approx(-0.5)


def test_snapshot_web_units_without_factor_or_wire_values():
    s = driver_session()
    s.arm("a", True)
    s.handle_cmd_vel("a", cmd(seq=3, vx=1.89, vy=0.0, wz=0.0))
    snap = s.snapshot()
    assert snap["cmd"] == {"vx": 1.89, "vy": 0.0, "wz": 0.0}
    assert snap["last_cmd_seq"] == 3
    text = repr(snap)
    assert "1.89" in text  # the web-unit value itself
    assert "divisor" not in text.lower()
    assert repr(1.0) not in repr(snap["cmd"])  # wire value is absent


def test_divisor_only_used_in_to_wire_units():
    import inspect

    src = inspect.getsource(control)
    body = inspect.getsource(control.to_wire_units)
    assert src.count("/ CMD_VEL_DIVISOR") == 3
    assert body.count("/ CMD_VEL_DIVISOR") == 3


# ---- no clamping (SAF-04) ----

@pytest.mark.parametrize("big", [5.0, 100.0, -250.0, 1e6])
def test_no_speed_limit(big):
    s = driver_session()
    s.arm("a", True)
    out = s.handle_cmd_vel("a", cmd(vx=big, vy=-big, wz=big))
    assert out["vx"] == pytest.approx(big / 1.89)
    assert out["vy"] == pytest.approx(-big / 1.89)
    assert out["wz"] == pytest.approx(big / 1.89)
    assert s.snapshot()["cmd"]["vx"] == big


# ---- validation ----

@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf])
@pytest.mark.parametrize("field", ["vx", "vy", "wz"])
def test_non_finite_rejected(bad, field):
    s = driver_session()
    s.arm("a", True)
    m = cmd()
    m[field] = bad
    with pytest.raises(ValueError):
        s.handle_cmd_vel("a", m)
    assert s.snapshot()["last_cmd_seq"] is None


@pytest.mark.parametrize("bad", ["1", None, True, [1], {"a": 1}])
def test_wrong_types_rejected(bad):
    for field in ("vx", "vy", "wz"):
        m = cmd()
        m[field] = bad
        with pytest.raises(ValueError):
            validate_cmd_vel(m)


@pytest.mark.parametrize("seq", [None, "1", 1.5, True, -1])
def test_bad_seq_rejected(seq):
    with pytest.raises(ValueError):
        validate_cmd_vel(cmd(seq=seq))


def test_missing_field_and_non_dict_rejected():
    with pytest.raises(ValueError):
        validate_cmd_vel({"seq": 1, "vx": 0.0, "vy": 0.0})
    with pytest.raises(ValueError):
        validate_cmd_vel([1, 2, 3])


def test_int_values_accepted():
    assert validate_cmd_vel(cmd(seq=1, vx=1, vy=0, wz=0)) == (1, 1.0, 0.0, 0.0)


# ---- single operator, viewers read-only ----

def test_wrong_token_is_viewer_only():
    s = make_session()
    s.connect("a", ORIGIN)
    assert s.hello("a", "wrong") is False
    assert s.hello("a", None) is False
    assert s.role("a") == "viewer"
    assert s.arm("a", True) is False
    assert s.armed is False


def test_only_one_driver():
    s = driver_session()
    s.connect("b", ORIGIN)
    assert s.hello("b", "secret") is False
    assert s.role("a") == "driver"
    assert s.role("b") == "viewer"
    s.arm("a", True)
    assert s.handle_cmd_vel("b", cmd(vx=1.0)) is None
    assert s.handle_cmd_vel("a", cmd(vx=1.0)) is not None


def test_driver_hello_again_ok():
    s = driver_session()
    assert s.hello("a", "secret") is True


def test_driver_disconnect_disarms_and_signals_zero():
    s = driver_session()
    s.arm("a", True)
    s.handle_cmd_vel("a", cmd(vx=1.0))
    assert s.disconnect("a") is True
    assert s.armed is False
    assert s.driver is None
    assert s.snapshot()["cmd"] == {"vx": 0.0, "vy": 0.0, "wz": 0.0}
    s.connect("b", ORIGIN)
    assert s.hello("b", "secret") is True
    assert s.armed is False  # new driver still starts disarmed


def test_viewer_disconnect_keeps_state():
    s = driver_session()
    s.arm("a", True)
    s.connect("v", ORIGIN)
    assert s.disconnect("v") is False
    assert s.armed is True
    assert s.role("v") is None


def test_unknown_client_cannot_hello():
    s = make_session()
    assert s.hello("ghost", "secret") is False


# ---- token and origin ----

def test_token_matches():
    assert token_matches("secret", "secret") is True
    assert token_matches("secreT", "secret") is False
    assert token_matches("", "") is False
    assert token_matches(None, "secret") is False
    assert token_matches(123, "secret") is False
    assert token_matches("sécret", "secret") is False
    assert token_matches("\ud800", "secret") is False


def test_token_compare_is_constant_time():
    import inspect

    assert "compare_digest" in inspect.getsource(control.token_matches)


def test_origin_allowed():
    assert origin_allowed(ORIGIN, [ORIGIN]) is True
    assert origin_allowed("http://evil.example", [ORIGIN]) is False
    assert origin_allowed(None, [ORIGIN]) is False
    assert origin_allowed("", [ORIGIN]) is False
    assert origin_allowed(ORIGIN, []) is False


def test_bad_origin_rejected_on_connect():
    s = make_session()
    assert s.connect("x", "http://evil.example") is False
    assert s.connect("y", None) is False
    assert s.role("x") is None
    assert s.hello("x", "secret") is False


# ---- watchdog (SAF-03b) ----

def test_watchdog_trips_at_250ms_once():
    clock = FakeClock()
    s = driver_session(clock)
    s.arm("a", True)
    assert s.watchdog_tripped() is False  # nothing received yet
    s.handle_cmd_vel("a", cmd(vx=1.0))
    clock.t += 0.249
    assert s.watchdog_tripped() is False
    clock.t += 0.001
    assert s.watchdog_tripped() is True
    assert s.watchdog_tripped() is False
    assert s.snapshot()["cmd"] == {"vx": 0.0, "vy": 0.0, "wz": 0.0}
    assert s.armed is True


def test_watchdog_reset_by_new_command():
    clock = FakeClock()
    s = driver_session(clock)
    s.arm("a", True)
    s.handle_cmd_vel("a", cmd(seq=1, vx=1.0))
    clock.t += 0.2
    s.handle_cmd_vel("a", cmd(seq=2, vx=1.0))
    clock.t += 0.2
    assert s.watchdog_tripped() is False
    clock.t += 0.06
    assert s.watchdog_tripped() is True


def test_rejected_commands_do_not_feed_watchdog():
    clock = FakeClock()
    s = driver_session(clock)
    s.arm("a", True)
    s.handle_cmd_vel("a", cmd(vx=1.0))
    s.connect("b", ORIGIN)
    clock.t += 0.2
    assert s.handle_cmd_vel("b", cmd(seq=2, vx=1.0)) is None
    with pytest.raises(ValueError):
        s.handle_cmd_vel("a", cmd(seq=3, vx=math.nan))
    clock.t += 0.06
    assert s.watchdog_tripped() is True


def test_default_clock_is_monotonic():
    import inspect
    import time

    default = inspect.signature(ControlSession.__init__).parameters["clock"].default
    assert default is time.monotonic


@pytest.mark.parametrize("field", ["vx", "vy", "wz"])
@pytest.mark.parametrize("huge", [10**330, 10**400])
def test_validate_cmd_vel_rejects_overflowing_int(field, huge):
    msg = {"seq": 1, "vx": 0.0, "vy": 0.0, "wz": 0.0}
    msg[field] = huge
    with pytest.raises(ValueError):
        validate_cmd_vel(msg)


# ======================================================================================
# T06: odometry, telemetry, robot link, operator WebSocket
# ======================================================================================

LINK_TOKEN = "link"
OPERATOR_TOKEN = "secret"
NS = 1_000_000_000
STEP_NS = 100_000_000  # 0.1 s
WIRE_VEL = (0.1234, 0.0567, 0.0891)  # distinctive wire-unit values sent by the fake robot


def robot_state(t_ns=0, vel=WIRE_VEL, seq=None):
    """A robot `state` message as PROTO-2 describes it (velocities in wire units)."""
    return {
        "t": "state",
        "t_mono_ns": t_ns,
        "last_cmd_seq": seq,
        "vel": None if vel is None else {"vx": vel[0], "vy": vel[1], "wz": vel[2]},
        "imu": {"ax": 0.01, "ay": 0.02, "az": 9.81, "gx": 0.003, "gy": 0.004, "gz": 0.005},
        "voltage": 12.3,
        "flag_stop": 0,
        "charge": None,
        "health": {
            "stm": {"ok": True, "state": "ok", "error": None, "restarts": 0},
            "lidar": {"ok": True, "state": "ok", "error": None, "restarts": 0},
            "writer": {
                "running": True,
                "healthy": True,
                "error_count": 0,
                "last_error": None,
                "rejected_count": 0,
            },
        },
    }


def is_zero(command):
    return command["vx"] == 0 and command["vy"] == 0 and command["wz"] == 0


async def wait_until(condition, timeout=3.0, step=0.01):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return
        await asyncio.sleep(step)
    raise AssertionError("condition not met in time")


# ---- odometry (PHY-7) ----


def test_odometry_first_sample_does_not_move():
    o = Odometry()
    assert o.update(5 * NS, 1.0, 1.0, 1.0) is False
    assert o.pose() == {"x": 0.0, "y": 0.0, "theta": 0.0}


def test_odometry_straight_ahead():
    o = Odometry()
    o.update(0, 0.0, 0.0, 0.0)
    assert o.update(STEP_NS, 0.5, 0.0, 0.0) is True
    assert o.x == pytest.approx(0.05)
    assert o.y == pytest.approx(0.0)
    assert o.theta == pytest.approx(0.0)


def test_odometry_sideways_is_body_y():
    o = Odometry()
    o.update(0, 0.0, 0.0, 0.0)
    o.update(STEP_NS, 0.0, 1.0, 0.0)
    assert o.x == pytest.approx(0.0, abs=1e-12)
    assert o.y == pytest.approx(0.1)


def test_odometry_midpoint_heading():
    o = Odometry()
    o.update(0, 0.0, 0.0, 0.0)
    o.update(STEP_NS, 1.0, 0.0, 2.0)  # rotates 0.2 rad, heading used for motion is 0.1
    assert o.theta == pytest.approx(0.2)
    assert o.x == pytest.approx(0.1 * math.cos(0.1))
    assert o.y == pytest.approx(0.1 * math.sin(0.1))


def test_odometry_body_to_world_when_rotated():
    o = Odometry()
    o.theta = math.pi / 2
    o.update(0, 0.0, 0.0, 0.0)
    o.update(STEP_NS, 1.0, 0.0, 0.0)  # body x points along world y
    assert o.x == pytest.approx(0.0, abs=1e-12)
    assert o.y == pytest.approx(0.1)
    o.update(2 * STEP_NS, 0.0, 1.0, 0.0)  # body y points along world -x
    assert o.x == pytest.approx(-0.1)
    assert o.y == pytest.approx(0.1)


def test_odometry_accumulates_steps():
    o = Odometry()
    for i in range(11):
        o.update(i * STEP_NS, 0.5, 0.0, 0.0)
    assert o.x == pytest.approx(0.5)


@pytest.mark.parametrize("dt_ns", [0, -1_000_000, 500_000_001, 600_000_000, 5 * NS])
def test_odometry_skips_bad_dt(dt_ns):
    o = Odometry()
    o.update(10 * NS, 0.0, 0.0, 0.0)
    assert o.update(10 * NS + dt_ns, 1.0, 1.0, 1.0) is False
    assert o.pose() == {"x": 0.0, "y": 0.0, "theta": 0.0}


def test_odometry_dt_of_exactly_half_second_is_integrated():
    o = Odometry()
    o.update(0, 0.0, 0.0, 0.0)
    assert o.update(500_000_000, 1.0, 0.0, 0.0) is True
    assert o.x == pytest.approx(0.5)


def test_odometry_resumes_after_a_gap_from_the_skipped_sample():
    o = Odometry()
    o.update(0, 1.0, 0.0, 0.0)
    assert o.update(1 * NS, 1.0, 0.0, 0.0) is False  # 1 s gap
    assert o.update(1 * NS + STEP_NS, 1.0, 0.0, 0.0) is True  # dt 0.1 s, not 1.1 s
    assert o.x == pytest.approx(0.1)


def test_odometry_resyncs_when_the_robot_clock_goes_backwards():
    o = Odometry()
    o.update(10 * NS, 1.0, 0.0, 0.0)
    assert o.update(5 * NS, 1.0, 0.0, 0.0) is False
    assert o.update(5 * NS + STEP_NS, 1.0, 0.0, 0.0) is True
    assert o.x == pytest.approx(0.1)


@pytest.mark.parametrize("bad", [math.nan, math.inf])
def test_odometry_skips_non_finite_velocity(bad):
    o = Odometry()
    o.update(0, 0.0, 0.0, 0.0)
    assert o.update(STEP_NS, bad, 0.0, 0.0) is False
    assert o.pose() == {"x": 0.0, "y": 0.0, "theta": 0.0}


def test_odometry_theta_wraps():
    o = Odometry()
    o.update(0, 0.0, 0.0, 0.0)
    o.update(STEP_NS, 0.0, 0.0, 40.0)  # +4 rad in one step
    assert -math.pi <= o.theta < math.pi
    assert o.theta == pytest.approx(math.atan2(math.sin(4.0), math.cos(4.0)))


def test_odometry_reset():
    o = Odometry()
    o.update(0, 1.0, 0.0, 1.0)
    o.update(STEP_NS, 1.0, 0.0, 1.0)
    assert o.x != 0.0
    o.reset()
    assert o.pose() == {"x": 0.0, "y": 0.0, "theta": 0.0}
    assert o.update(2 * STEP_NS, 1.0, 0.0, 0.0) is False  # first sample after a reset


# ---- telemetry: web units, state shape (SAF-01, PROTO-1) ----

SNAPSHOT = {
    "armed": False,
    "has_driver": False,
    "cmd": {"vx": 0.0, "vy": 0.0, "wz": 0.0},
    "last_cmd_seq": None,
}


def test_telemetry_vel_is_multiplied_imu_is_not():
    t = Telemetry()
    t.on_robot_state(robot_state(vel=(0.1, 0.0, 0.0), seq=4))
    state = t.build_state(SNAPSHOT, True)
    assert state["vel"]["vx"] == pytest.approx(0.189)
    assert state["vel"]["vy"] == 0.0
    assert state["imu"] == {"ax": 0.01, "ay": 0.02, "az": 9.81, "gx": 0.003, "gy": 0.004,
                            "gz": 0.005}
    assert state["voltage"] == 12.3
    assert state["flag_stop"] == 0
    assert state["last_cmd_seq"] == 4
    assert state["health"]["writer"]["running"] is True


def test_telemetry_state_has_exactly_the_proto1_fields():
    state = Telemetry().build_state(SNAPSHOT, False)
    assert set(state) == {"t", "link", "session", "vel", "pose", "cmd", "imu", "voltage",
                          "flag_stop", "charge", "health", "last_cmd_seq"}
    assert state["t"] == "state"
    assert state["link"] == {"robot": False, "rtt_ms": None}
    assert state["session"] == {"armed": False, "has_driver": False}
    assert state["vel"] is None and state["imu"] is None
    assert state["pose"] == {"x": 0.0, "y": 0.0, "theta": 0.0}


def test_telemetry_rtt_in_milliseconds():
    assert Telemetry().build_state(SNAPSHOT, True, 0.0123)["link"]["rtt_ms"] == 12.3


def test_telemetry_ignores_malformed_fields():
    t = Telemetry()
    msg = robot_state()
    msg["vel"] = {"vx": "fast", "vy": 0.0, "wz": 0.0}
    msg["imu"] = {"ax": math.nan, "ay": 0, "az": 0, "gx": 0, "gy": 0, "gz": 0}
    msg["voltage"] = math.inf
    msg["last_cmd_seq"] = True
    t.on_robot_state(msg)
    state = t.build_state(SNAPSHOT, True)
    assert state["vel"] is None and state["imu"] is None
    assert state["voltage"] is None and state["last_cmd_seq"] is None
    json.dumps(state, allow_nan=False)


def test_telemetry_odometry_uses_scaled_vel_and_robot_time():
    t = Telemetry()
    t.on_robot_state(robot_state(t_ns=0, vel=(0.5, 0.0, 0.0)))
    t.on_robot_state(robot_state(t_ns=STEP_NS, vel=(0.5, 0.0, 0.0)))
    t.on_robot_state(robot_state(t_ns=2 * STEP_NS, vel=(0.5, 0.0, 0.0)))
    assert t.build_state(SNAPSHOT, True)["pose"]["x"] == pytest.approx(0.189)


def test_telemetry_clear_robot_keeps_pose_and_reset_clears_it():
    t = Telemetry()
    t.on_robot_state(robot_state(t_ns=0, vel=(0.5, 0.0, 0.0)))
    t.on_robot_state(robot_state(t_ns=STEP_NS, vel=(0.5, 0.0, 0.0)))
    t.clear_robot()
    state = t.build_state(SNAPSHOT, False)
    assert state["vel"] is None and state["imu"] is None and state["health"] is None
    assert state["pose"]["x"] == pytest.approx(0.0945)
    t.reset_odometry()
    assert t.build_state(SNAPSHOT, False)["pose"] == {"x": 0.0, "y": 0.0, "theta": 0.0}


def test_telemetry_uses_the_control_constant_only():
    import inspect

    from app_server import robot_link

    assert telemetry_module.CMD_VEL_DIVISOR is control.CMD_VEL_DIVISOR
    assert inspect.getsource(telemetry_module).count("* CMD_VEL_DIVISOR") == 1
    for module in (telemetry_module, app_main, robot_link):
        source = inspect.getsource(module)
        assert "1.89" not in source
    for module in (app_main, robot_link):
        assert "CMD_VEL_DIVISOR" not in inspect.getsource(module)


# ---- test doubles: a fake robot WebSocket server and the app under uvicorn ----


class FakeRobot:
    """A robot WS server that records what the app sends and can push states."""

    def __init__(self, token=LINK_TOKEN):
        self.token = token
        self.received = []
        self.first_messages = []
        self.auth_headers = []
        self.connections = []
        self.attempts = 0
        self.refuse = False  # True: answer every handshake with 503
        self.port = None
        self._server = None

    @property
    def url(self):
        return "ws://127.0.0.1:%d/ws" % self.port

    def _process_request(self, connection, request):
        self.attempts += 1
        header = request.headers.get("Authorization")
        self.auth_headers.append(header)
        if self.refuse:
            return connection.respond(HTTPStatus.SERVICE_UNAVAILABLE, "down\n")
        if header != "Bearer " + self.token:
            return connection.respond(HTTPStatus.UNAUTHORIZED, "unauthorized\n")
        return None

    async def _handler(self, conn):
        self.connections.append(conn)
        first = True
        try:
            async for message in conn:
                data = json.loads(message)
                if first:
                    self.first_messages.append(data)
                    first = False
                self.received.append(data)
        except ConnectionClosed:
            pass

    async def start(self, port=0):
        self._server = await serve(
            self._handler, "127.0.0.1", port, process_request=self._process_request
        )
        self.port = self._server.sockets[0].getsockname()[1]

    async def stop(self):
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

    def live(self):
        return [c for c in self.connections if c.state is State.OPEN]

    async def drop(self):
        for conn in self.live():
            await conn.close()

    async def send_binary(self, data):
        live = self.live()
        if live:
            await live[-1].send(data)

    async def send_state(self, message):
        live = self.live()
        if live:
            await live[-1].send(json.dumps(message))

    def cmds(self):
        return [m for m in self.received if m.get("t") == "cmd_vel"]


@pytest.fixture
async def robot():
    fake = FakeRobot()
    await fake.start()
    yield fake
    await fake.stop()


@asynccontextmanager
async def running_app(robot_url, clock=None):
    settings = load_settings(
        {
            "ROBOT_LINK_TOKEN": LINK_TOKEN,
            "OPERATOR_TOKEN": OPERATOR_TOKEN,
            "ROBOT_WS_URL": robot_url,
            "APP_ALLOWED_ORIGINS": ORIGIN,
        }
    )
    app = create_app(
        settings, clock=clock or time.monotonic, backoff_initial_s=0.02, backoff_max_s=0.1
    )
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
        yield SimpleNamespace(
            ws_url="ws://127.0.0.1:%d/ws/operator" % port,
            http_url="http://127.0.0.1:%d" % port,
            runtime=app.state.runtime,
        )
    finally:
        server.should_exit = True
        await asyncio.wait_for(task, 10)


@asynccontextmanager
async def operator(app, drive=True, origin=ORIGIN):
    async with connect(app.ws_url, origin=origin) as ws:
        if drive:
            await send(ws, t="hello", token=OPERATOR_TOKEN)
        yield ws


async def send(ws, **message):
    await ws.send(json.dumps(message))


async def state_where(ws, predicate, timeout=3.0):
    deadline = time.monotonic() + timeout
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise AssertionError("no matching state received")
        message = json.loads(await asyncio.wait_for(ws.recv(), remaining))
        if message.get("t") == "state" and predicate(message):
            return message


async def arm_as_driver(ws, app):
    await wait_until(lambda: app.runtime.link.connected)
    await state_where(ws, lambda s: s["session"]["role"] == "driver" and s["link"]["robot"])
    await send(ws, t="arm", on=True)
    await state_where(ws, lambda s: s["session"]["armed"])


async def drain_states(ws, seconds):
    """Every state received during the next `seconds`."""
    states = []
    deadline = time.monotonic() + seconds
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return states
        try:
            message = json.loads(await asyncio.wait_for(ws.recv(), remaining))
        except asyncio.TimeoutError:
            return states
        if message.get("t") == "state":
            states.append(message)


def nonzero(robot):
    return [c for c in robot.cmds() if not is_zero(c)]


def zeros(robot):
    return [c for c in robot.cmds() if is_zero(c)]


def numbers_and_keys(value, key=""):
    """Yield (key, number) for every numeric leaf and (key, None) for every dict key."""
    if isinstance(value, dict):
        for k, v in value.items():
            yield k, None
            yield from numbers_and_keys(v, k)
    elif isinstance(value, list):
        for v in value:
            yield from numbers_and_keys(v, key)
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        yield key, value


def assert_web_units_only(texts, wire_values):
    """No payload may hold a wire-unit value, the factor, its inverse, or a telling key."""
    forbidden = tuple(wire_values) + (1.89, 1 / 1.89)
    for text in texts:
        assert "1.89" not in text
        for key, number in numbers_and_keys(json.loads(text)):
            assert not any(w in key.lower() for w in ("wire", "divisor", "factor", "scale"))
            if number is not None:
                assert not any(math.isclose(number, f, rel_tol=1e-6) for f in forbidden)


# ---- Hub: a slow client must not block the others ----


def scan_frame(seq, mm=1500):
    """A PROTO-2 scan frame: type 2, ver 1, seq, t_mono_ms, 360 x u16 mm."""
    return struct.pack("<BBIQ", 2, 1, seq, seq * 100) + struct.pack("<360H", *([mm] * 360))


class FakeWs:
    def __init__(self, blocked=False):
        self.sent = []
        self.gate = asyncio.Event()
        if not blocked:
            self.gate.set()

    async def send_text(self, text):
        await self.gate.wait()
        self.sent.append(text)

    async def send_bytes(self, data):
        await self.gate.wait()
        self.sent.append(data)


async def test_slow_client_gets_only_the_latest_and_blocks_nobody():
    hub = Hub()
    fast, slow = FakeWs(), FakeWs(blocked=True)
    hub.add("fast", fast)
    hub.add("slow", slow)
    base = Telemetry().build_state(SNAPSHOT, True)
    for n in range(1, 6):
        hub.publish(dict(base, last_cmd_seq=n), lambda _cid: "viewer")
        await asyncio.sleep(0.01)
    assert [json.loads(t)["last_cmd_seq"] for t in fast.sent] == [1, 2, 3, 4, 5]
    assert slow.sent == []
    slow.gate.set()
    await wait_until(lambda: len(slow.sent) == 2)
    assert [json.loads(t)["last_cmd_seq"] for t in slow.sent] == [1, 5]  # in flight + latest
    hub.remove("fast")
    hub.remove("slow")


async def test_slow_client_gets_only_the_latest_scan_and_blocks_nobody():
    hub = Hub()
    fast, slow = FakeWs(), FakeWs(blocked=True)
    hub.add("fast", fast)
    hub.add("slow", slow)
    for n in range(1, 6):
        hub.publish_scan(scan_frame(n))
        await asyncio.sleep(0.01)
    assert fast.sent == [scan_frame(n) for n in range(1, 6)]
    assert slow.sent == []
    slow.gate.set()
    await wait_until(lambda: len(slow.sent) == 2)
    assert slow.sent == [scan_frame(1), scan_frame(5)]  # in flight + latest, no backlog
    hub.remove("fast")
    hub.remove("slow")


async def test_hub_adds_each_clients_own_role():
    hub = Hub()
    a, b = FakeWs(), FakeWs()
    hub.add("a", a)
    hub.add("b", b)
    hub.publish(Telemetry().build_state(SNAPSHOT, True), {"a": "driver", "b": "viewer"}.get)
    await wait_until(lambda: a.sent and b.sent)
    assert json.loads(a.sent[0])["session"]["role"] == "driver"
    assert json.loads(b.sent[0])["session"]["role"] == "viewer"
    hub.remove("a")
    hub.remove("b")


# ---- RobotLink ----


async def test_link_connects_with_bearer_and_sends_exact_keys(robot):
    states = []
    link = RobotLink(robot.url, LINK_TOKEN, on_state=states.append, backoff_initial_s=0.02)
    task = asyncio.ensure_future(link.run())
    try:
        await wait_until(lambda: link.connected)
        assert robot.auth_headers[-1] == "Bearer " + LINK_TOKEN
        assert link.send_cmd_vel(3, 0.1, -0.2, 0.05) is True
        await wait_until(lambda: robot.cmds())
        assert robot.cmds()[0] == {"t": "cmd_vel", "seq": 3, "vx": 0.1, "vy": -0.2, "wz": 0.05}
        await robot.send_state(robot_state(t_ns=7))
        await wait_until(lambda: states)
        assert states[0]["t_mono_ns"] == 7
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


async def test_link_keeps_only_the_latest_command(robot):
    link = RobotLink(robot.url, LINK_TOKEN, on_state=lambda m: None, backoff_initial_s=0.02)
    task = asyncio.ensure_future(link.run())
    try:
        await wait_until(lambda: link.connected)
        for seq in range(1000):  # no await: the sender cannot run in between
            link.send_cmd_vel(seq, 0.1, 0.0, 0.0)
        await wait_until(lambda: robot.cmds())
        await asyncio.sleep(0.05)
        assert [c["seq"] for c in robot.cmds()] == [999]
        link.send_cmd_vel(1000, 0.1, 0.0, 0.0)
        link.send_zero()  # a zero replaces an unsent command
        await wait_until(lambda: len(robot.cmds()) == 2)
        await asyncio.sleep(0.05)
        assert is_zero(robot.cmds()[1]) and len(robot.cmds()) == 2
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


async def test_link_reconnects_and_never_replays_an_old_command(robot):
    events = []
    link = RobotLink(
        robot.url,
        LINK_TOKEN,
        on_state=lambda m: None,
        on_connect=lambda: events.append("up"),
        on_disconnect=lambda: events.append("down"),
        backoff_initial_s=0.02,
        backoff_max_s=0.1,
    )
    task = asyncio.ensure_future(link.run())
    try:
        await wait_until(lambda: link.connected)
        await robot.drop()
        await wait_until(lambda: "down" in events)
        assert link.connected is False
        assert link.send_cmd_vel(5, 0.1, 0.0, 0.0) is False  # dropped, not queued
        await wait_until(lambda: link.connected)  # reconnected by itself
        assert events == ["up", "down", "up"]
        await asyncio.sleep(0.1)
        assert robot.cmds() == []  # nothing from before the drop was replayed
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


async def test_link_retries_while_the_robot_is_unreachable():
    fake = FakeRobot()
    await fake.start()
    port = fake.port
    await fake.stop()
    link = RobotLink(
        "ws://127.0.0.1:%d/ws" % port,
        LINK_TOKEN,
        on_state=lambda m: None,
        backoff_initial_s=0.02,
        backoff_max_s=0.1,
    )
    task = asyncio.ensure_future(link.run())
    try:
        await asyncio.sleep(0.2)
        assert link.connected is False
        await fake.start(port=port)
        await wait_until(lambda: link.connected, timeout=5.0)
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        await fake.stop()


async def test_link_with_wrong_token_never_connects():
    fake = FakeRobot(token="other")
    await fake.start()
    link = RobotLink(fake.url, LINK_TOKEN, on_state=lambda m: None, backoff_initial_s=0.02)
    task = asyncio.ensure_future(link.run())
    try:
        await wait_until(lambda: fake.attempts >= 3)  # it keeps retrying
        assert link.connected is False
        assert fake.live() == []
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        await fake.stop()


# ---- app server over a real socket ----


async def test_health_endpoint(robot):
    async with running_app(robot.url) as app:
        await wait_until(lambda: app.runtime.link.connected)
        async with httpx.AsyncClient() as client:
            response = await client.get(app.http_url + "/health")
        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True and body["robot_link"] is True
        assert_web_units_only([response.text], WIRE_VEL)


async def test_bad_or_missing_origin_is_refused_before_accept(robot):
    async with running_app(robot.url) as app:
        for origin in ("http://evil.example", None):
            with pytest.raises(InvalidStatus) as info:
                async with connect(app.ws_url, origin=origin):
                    pass
            assert info.value.response.status_code == 403
        assert len(app.runtime.hub) == 0
        assert app.runtime.session.driver is None


async def test_web_command_reaches_robot_in_wire_units(robot):
    async with running_app(robot.url) as app:
        async with operator(app) as ws:
            await arm_as_driver(ws, app)
            await send(ws, t="cmd_vel", seq=7, vx=0.189, vy=-0.378, wz=0.0945, src="kbd")
            await wait_until(lambda: nonzero(robot))
            command = nonzero(robot)[0]
            assert set(command) == {"t", "seq", "vx", "vy", "wz"}  # src stripped
            assert command["seq"] == 7
            assert command["vx"] == pytest.approx(0.1)
            assert command["vy"] == pytest.approx(-0.2)
            assert command["wz"] == pytest.approx(0.05)
            state = await state_where(ws, lambda s: s["cmd"]["vx"] != 0.0)
            assert state["cmd"] == {"vx": 0.189, "vy": -0.378, "wz": 0.0945}  # web units


async def test_state_is_in_web_units_and_passes_last_cmd_seq(robot):
    async with running_app(robot.url) as app:
        async with operator(app, drive=False) as ws:
            await wait_until(lambda: app.runtime.link.connected)
            await robot.send_state(robot_state(t_ns=1, vel=(0.1, 0.05, 0.2), seq=42))
            state = await state_where(ws, lambda s: s["vel"] is not None)
            assert state["vel"]["vx"] == pytest.approx(0.189)
            assert state["vel"]["vy"] == pytest.approx(0.0945)
            assert state["vel"]["wz"] == pytest.approx(0.378)
            assert state["imu"]["az"] == 9.81  # IMU is not scaled
            assert state["last_cmd_seq"] == 42
            assert state["link"]["robot"] is True
            assert state["session"]["role"] == "viewer"
            assert state["pose"] == {"x": 0.0, "y": 0.0, "theta": 0.0}


async def test_state_rate_is_at_most_20_hz(robot):
    async with running_app(robot.url) as app:
        async with operator(app, drive=False) as ws:
            await wait_until(lambda: app.runtime.link.connected)
            stop = False

            async def flood():
                t_ns = 0
                while not stop:
                    await robot.send_state(robot_state(t_ns=t_ns))
                    t_ns += 5_000_000
                    await asyncio.sleep(0.005)

            flooder = asyncio.ensure_future(flood())
            count = 0
            started = time.monotonic()
            try:
                while time.monotonic() - started < 0.8:
                    await asyncio.wait_for(ws.recv(), 2.0)
                    count += 1
            finally:
                stop = True
                await asyncio.gather(flooder, return_exceptions=True)
            elapsed = time.monotonic() - started
            assert 5 <= count <= 20 * elapsed + 2


async def test_no_wire_values_or_factor_in_any_web_payload(robot):
    async with running_app(robot.url) as app:
        async with operator(app) as ws:
            await arm_as_driver(ws, app)
            await send(ws, t="cmd_vel", seq=1, vx=0.3402, vy=0.0, wz=0.0)  # wire 0.18
            await wait_until(lambda: nonzero(robot))
            for n in range(4):
                await robot.send_state(robot_state(t_ns=n * STEP_NS, seq=1))
            texts = []
            deadline = time.monotonic() + 0.6
            while time.monotonic() < deadline:
                try:
                    texts.append(await asyncio.wait_for(ws.recv(), 0.2))
                except asyncio.TimeoutError:
                    break
            assert len(texts) >= 5
            assert any(json.loads(t)["vel"] is not None for t in texts)
            assert_web_units_only(texts, WIRE_VEL + (0.18,))


async def test_watchdog_sends_zero_after_250ms_without_commands(robot):
    clock = FakeClock()
    async with running_app(robot.url, clock) as app:
        async with operator(app) as ws:
            await arm_as_driver(ws, app)
            await send(ws, t="cmd_vel", seq=1, vx=0.189, vy=0.0, wz=0.0)
            await wait_until(lambda: nonzero(robot))
            before = len(zeros(robot))
            clock.t += 0.24
            await asyncio.sleep(0.15)  # several watchdog ticks
            assert len(zeros(robot)) == before  # not yet
            clock.t += 0.02
            await wait_until(lambda: len(zeros(robot)) == before + 1)
            await asyncio.sleep(0.15)
            assert len(zeros(robot)) == before + 1  # once, not repeatedly
            state = await state_where(ws, lambda s: s["cmd"]["vx"] == 0.0)
            assert state["session"]["armed"] is True  # the watchdog stops, it does not disarm


async def test_operator_disconnect_sends_zero_and_disarms(robot):
    async with running_app(robot.url) as app:
        async with operator(app) as ws:
            await arm_as_driver(ws, app)
            await send(ws, t="cmd_vel", seq=1, vx=0.189, vy=0.0, wz=0.0)
            await wait_until(lambda: nonzero(robot))
            before = len(zeros(robot))
        await wait_until(lambda: len(zeros(robot)) > before)
        assert app.runtime.session.armed is False
        assert app.runtime.session.driver is None
        async with operator(app, drive=False) as viewer:
            state = await state_where(viewer, lambda s: True)
            assert state["session"]["armed"] is False
            assert state["session"]["has_driver"] is False


async def test_disarm_sends_zero(robot):
    async with running_app(robot.url) as app:
        async with operator(app) as ws:
            await arm_as_driver(ws, app)
            before = len(zeros(robot))
            await send(ws, t="arm", on=False)
            await wait_until(lambda: len(zeros(robot)) > before)
            await state_where(ws, lambda s: not s["session"]["armed"])


async def test_arm_is_refused_while_the_robot_link_is_down():
    fake = FakeRobot()
    await fake.start()
    url = fake.url
    await fake.stop()
    async with running_app(url) as app:
        async with operator(app) as ws:
            await state_where(ws, lambda s: s["session"]["role"] == "driver")
            await send(ws, t="arm", on=True)
            states = await drain_states(ws, 0.2)
            assert len(states) >= 2
            assert all(s["session"]["armed"] is False for s in states)
            assert all(s["link"]["robot"] is False for s in states)


async def test_link_loss_disarms_and_old_commands_do_not_resume(robot):
    async with running_app(robot.url) as app:
        async with operator(app) as ws:
            await arm_as_driver(ws, app)
            await send(ws, t="cmd_vel", seq=1, vx=0.189, vy=0.0, wz=0.0)
            await wait_until(lambda: nonzero(robot))
            robot.refuse = True  # keep the link down long enough to observe it
            await robot.drop()
            lost = await state_where(ws, lambda s: not s["link"]["robot"])
            assert lost["session"]["armed"] is False
            assert lost["vel"] is None and lost["imu"] is None
            robot.refuse = False
            back = await state_where(ws, lambda s: s["link"]["robot"])
            assert back["session"]["armed"] is False  # reconnected, still disarmed
            await wait_until(lambda: len(robot.first_messages) == 2)
            assert is_zero(robot.first_messages[1])  # the new link starts with zero
            await send(ws, t="cmd_vel", seq=2, vx=0.189, vy=0.0, wz=0.0)
            await asyncio.sleep(0.15)
            assert [c["seq"] for c in nonzero(robot)] == [1]  # seq 2 was not forwarded
            await send(ws, t="arm", on=True)  # explicit re-arm restores control
            await state_where(ws, lambda s: s["session"]["armed"])
            await send(ws, t="cmd_vel", seq=3, vx=0.189, vy=0.0, wz=0.0)
            await wait_until(lambda: [c["seq"] for c in nonzero(robot)] == [1, 3])


async def test_viewer_may_watch_but_not_command(robot):
    async with running_app(robot.url) as app:
        async with operator(app) as driver, operator(app, drive=False) as viewer:
            await arm_as_driver(driver, app)
            await robot.send_state(robot_state(t_ns=0, vel=(0.5, 0.0, 0.0)))
            await robot.send_state(robot_state(t_ns=STEP_NS, vel=(0.5, 0.0, 0.0)))
            await robot.send_state(robot_state(t_ns=2 * STEP_NS, vel=(0.5, 0.0, 0.0)))
            moved = await state_where(viewer, lambda s: s["pose"]["x"] > 0.18)
            assert moved["pose"]["x"] == pytest.approx(0.189)
            assert moved["session"]["role"] == "viewer"
            await send(viewer, t="hello", token="wrong")
            await send(viewer, t="arm", on=False)
            await send(viewer, t="cmd_vel", seq=9, vx=0.189, vy=0.0, wz=0.0, src="kbd")
            await send(viewer, t="odom_reset")
            states = await drain_states(viewer, 0.2)
            assert len(states) >= 2
            assert all(s["session"]["armed"] for s in states)  # the viewer's arm(false) ignored
            assert all(s["pose"]["x"] == pytest.approx(0.189) for s in states)  # so was reset
            assert nonzero(robot) == []
            await send(driver, t="odom_reset")  # the driver may reset
            await state_where(viewer, lambda s: s["pose"]["x"] == 0.0)


async def test_second_operator_with_the_right_token_cannot_take_over(robot):
    async with running_app(robot.url) as app:
        async with operator(app) as first, operator(app) as second:
            await state_where(first, lambda s: s["session"]["role"] == "driver")
            await send(second, t="hello", token=OPERATOR_TOKEN)
            states = await drain_states(second, 0.2)
            assert len(states) >= 2
            assert all(s["session"]["role"] == "viewer" for s in states)
            assert app.runtime.session.driver is not None


async def test_malformed_messages_do_not_break_the_handler(robot):
    async with running_app(robot.url) as app:
        async with operator(app) as ws:
            await arm_as_driver(ws, app)
            junk = [
                "not json",
                "[1, 2, 3]",
                "123",
                "null",
                '"hello"',
                "{}",
                '{"t": 5}',
                '{"t": ["cmd_vel"]}',
                '{"t": "cmd_vel"}',
                '{"t": "cmd_vel", "seq": 1, "vx": "fast", "vy": 0, "wz": 0}',
                '{"t": "cmd_vel", "seq": -1, "vx": 0, "vy": 0, "wz": 0}',
                '{"t": "cmd_vel", "seq": 1, "vx": NaN, "vy": 0, "wz": 0}',
                '{"t": "arm", "on": "yes"}',
                '{"t": "hello", "token": 5}',
                "x" * 5000,
                "[" * 100000,
            ]
            for text in junk:
                await ws.send(text)
            await ws.send(b"\x00\x01binary")
            await send(ws, t="cmd_vel", seq=11, vx=0.189, vy=0.0, wz=0.0)  # still works
            await wait_until(lambda: [c["seq"] for c in nonzero(robot)] == [11])
            state = await state_where(ws, lambda s: True)
            assert state["session"]["role"] == "driver" and state["session"]["armed"] is True


async def test_end_to_end_with_the_real_robot_server_and_simulator(robot):
    from robot_agent.drive import CmdVelWriter
    from robot_agent.server import RobotServer
    from robot_agent.sim import SimulatedStm32

    stm = SimulatedStm32()
    stm.start()
    writer = CmdVelWriter(stm, motion_enabled=True)
    healthy = {"ok": True, "state": "ok", "error": None, "restarts": 0}
    real = RobotServer(
        token=LINK_TOKEN, writer=writer, stm=stm, devices=lambda: {"stm": healthy, "lidar": healthy}
    )
    port = await real.start("127.0.0.1", 0)
    try:
        # A frozen clock keeps the app watchdog quiet, so the command stays in the mailbox.
        async with running_app("ws://127.0.0.1:%d/ws" % port, FakeClock()) as app:
            async with operator(app) as ws:
                await arm_as_driver(ws, app)
                await send(ws, t="cmd_vel", seq=5, vx=0.189, vy=0.0, wz=0.0, src="kbd")
                await wait_until(lambda: real.build_state()["last_cmd_seq"] == 5)
                assert writer.tick() == (pytest.approx(0.1), 0.0, 0.0)  # wire units at the robot
                assert stm.last_command[1] == pytest.approx(0.1)
                state = await state_where(ws, lambda s: s["vel"] and s["vel"]["vx"] > 0.185)
                assert state["vel"]["vx"] == pytest.approx(0.189, abs=0.005)  # web units again
                assert state["last_cmd_seq"] == 5
    finally:
        await real.close()
        stm.stop()


# ---- LiDAR scan relay (PROTO-2) ----


async def recv_binary(ws, timeout=2.0):
    deadline = time.monotonic() + timeout
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise AssertionError("no binary frame received")
        message = await asyncio.wait_for(ws.recv(), remaining)
        if isinstance(message, bytes):
            return message


async def test_scan_frame_reaches_operator_and_viewer_unchanged(robot):
    async with running_app(robot.url) as app:
        async with operator(app) as driver, operator(app, drive=False) as viewer:
            await wait_until(lambda: app.runtime.link.connected and len(app.runtime.hub) == 2)
            frame = scan_frame(7, mm=2345)
            await robot.send_binary(frame)
            assert await recv_binary(driver) == frame
            assert await recv_binary(viewer) == frame


async def test_malformed_binary_frames_are_not_forwarded(robot):
    async with running_app(robot.url) as app:
        async with operator(app, drive=False) as ws:
            await wait_until(lambda: app.runtime.link.connected)
            await robot.send_binary(scan_frame(1)[:-2])  # wrong size
            await robot.send_binary(b"\x09" + scan_frame(1)[1:])  # wrong type
            good = scan_frame(3)
            await robot.send_binary(good)
            assert await recv_binary(ws) == good  # the first binary frame seen is the valid one


async def test_scan_rate_is_at_most_10_hz_and_latest_only(robot):
    async with running_app(robot.url) as app:
        async with operator(app, drive=False) as ws:
            await wait_until(lambda: app.runtime.link.connected)
            stop = False

            async def flood():
                n = 0
                while not stop:
                    n += 1
                    await robot.send_binary(scan_frame(n))
                    await asyncio.sleep(0.005)

            flooder = asyncio.ensure_future(flood())
            seqs = []
            started = time.monotonic()
            try:
                while time.monotonic() - started < 1.0:
                    try:
                        message = await asyncio.wait_for(ws.recv(), 0.3)
                    except asyncio.TimeoutError:
                        continue
                    if isinstance(message, bytes):
                        seqs.append(struct.unpack_from("<I", message, 2)[0])
            finally:
                stop = True
                await asyncio.gather(flooder, return_exceptions=True)
            elapsed = time.monotonic() - started
            assert 5 <= len(seqs) <= 10 * elapsed + 1
            assert seqs == sorted(set(seqs))  # newest wins, never repeated or reordered


async def test_scans_do_not_delay_state_or_commands(robot):
    async with running_app(robot.url) as app:
        async with operator(app) as ws:
            await arm_as_driver(ws, app)
            for n in range(20):
                await robot.send_binary(scan_frame(n))
            await send(ws, t="cmd_vel", seq=11, vx=0.189, vy=0.0, wz=0.0, src="kbd")
            await wait_until(lambda: any(c["seq"] == 11 for c in robot.cmds()), timeout=1.0)


# ---- entry point ----


def test_main_binds_to_the_configured_host_and_port(monkeypatch):
    captured = {}
    monkeypatch.setattr(app_main.uvicorn, "run", lambda app, **kwargs: captured.update(kwargs))
    env = {
        "ROBOT_LINK_TOKEN": "l",
        "OPERATOR_TOKEN": "o",
        "APP_BIND_HOST": "127.0.0.9",
        "APP_BIND_PORT": "8123",
    }
    app_main.main(env)
    assert captured["host"] == "127.0.0.9"
    assert captured["port"] == 8123


def test_main_refuses_to_start_without_tokens():
    with pytest.raises(ConfigError):
        app_main.main({"ROBOT_LINK_TOKEN": "", "OPERATOR_TOKEN": "o"})

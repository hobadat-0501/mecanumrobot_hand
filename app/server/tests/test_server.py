import math

import pytest

from app_server import control
from app_server.config import ConfigError, load_settings
from app_server.control import (
    CMD_VEL_DIVISOR,
    ControlSession,
    origin_allowed,
    to_wire_units,
    token_matches,
    validate_cmd_vel,
)

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

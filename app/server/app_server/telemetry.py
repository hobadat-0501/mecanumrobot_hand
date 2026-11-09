"""Telemetry: robot velocity, odometry (PHY-7), build the web `state`.

SAF-01: only `vel` is multiplied by the calibration scale (the same SPEED_SCALE control.py
divides by). IMU and every other field pass through unchanged.
"""

from __future__ import annotations

import math
from typing import Any, Dict, Optional

MAX_DT_S = 0.5  # PHY-7: samples further apart than this are not integrated
_NS_PER_S = 1e9
_IMU_KEYS = ("ax", "ay", "az", "gx", "gy", "gz")
# Limits for the free-form `health` and `charge` dicts the robot sends (forwarded to the web).
_MAX_DEPTH = 3  # a dict nested deeper than this is dropped
_MAX_ITEMS = 16  # keys kept per dict
_MAX_TEXT = 200  # characters kept per string or key
_MAX_INT = 2**53
_DROP = object()


def _finite(value: Any) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def _finite_dict(data: Any, keys: Any) -> Optional[Dict[str, float]]:
    """{key: float} when `data` is a dict with every key a finite number, else None."""
    if not isinstance(data, dict):
        return None
    out: Dict[str, float] = {}
    for key in keys:
        if not _finite(data.get(key)):
            return None
        out[key] = float(data[key])
    return out


def _clean(value: Any, depth: int = 0) -> Any:
    """A JSON-safe copy of `value`, or _DROP. Keeps None, bool, bounded numbers, short strings and
    bounded nested dicts; drops lists, non-finite numbers, non-str keys and anything else."""
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value if abs(value) <= _MAX_INT else _DROP
    if isinstance(value, float):
        return value if math.isfinite(value) else _DROP
    if isinstance(value, str):
        return value[:_MAX_TEXT]
    if isinstance(value, dict) and depth < _MAX_DEPTH:
        out: Dict[str, Any] = {}
        for key, item in value.items():
            if len(out) >= _MAX_ITEMS:
                break
            if not isinstance(key, str):
                continue
            cleaned = _clean(item, depth + 1)
            if cleaned is not _DROP:
                out[key[:_MAX_TEXT]] = cleaned
        return out
    return _DROP


def _clean_dict(value: Any) -> Optional[Dict[str, Any]]:
    """`_clean` for a field that must be a dict; None when it is not one."""
    cleaned = _clean(value)
    return cleaned if isinstance(cleaned, dict) else None


def _wrap_angle(theta: float) -> float:
    return (theta + math.pi) % (2.0 * math.pi) - math.pi


class Odometry:
    """Pose (x, y, theta) in the odometry frame, integrated with the midpoint heading."""

    def __init__(self) -> None:
        self.x = 0.0
        self.y = 0.0
        self.theta = 0.0
        self._last_t_ns: Optional[int] = None

    def reset(self) -> None:
        self.x = 0.0
        self.y = 0.0
        self.theta = 0.0
        self._last_t_ns = None

    def forget_time(self) -> None:
        """Keep the pose but treat the next sample as the first one."""
        self._last_t_ns = None

    def update(self, t_ns: int, vx: float, vy: float, wz: float) -> bool:
        """Integrate one sample (web units, robot t_mono_ns). True when the pose moved.

        The first sample, dt <= 0, dt > MAX_DT_S and non-finite velocities are skipped; the
        sample time is still remembered so the following sample integrates from it.
        """
        last = self._last_t_ns
        self._last_t_ns = t_ns
        if last is None:
            return False
        dt = (t_ns - last) / _NS_PER_S
        if dt <= 0.0 or dt > MAX_DT_S:
            return False
        if not (_finite(vx) and _finite(vy) and _finite(wz)):
            return False
        mid = self.theta + 0.5 * wz * dt
        cos_mid = math.cos(mid)
        sin_mid = math.sin(mid)
        x = self.x + (vx * cos_mid - vy * sin_mid) * dt
        y = self.y + (vx * sin_mid + vy * cos_mid) * dt
        theta = _wrap_angle(self.theta + wz * dt)
        if not (math.isfinite(x) and math.isfinite(y) and math.isfinite(theta)):
            return False  # never let the pose become inf or NaN (it goes to the web as JSON)
        self.x, self.y, self.theta = x, y, theta
        return True

    def pose(self) -> Dict[str, float]:
        return {"x": self.x, "y": self.y, "theta": self.theta}


class Telemetry:
    """Latest robot telemetry in web units plus odometry; builds the PROTO-1 `state`."""

    def __init__(self, speed_scale: float = 1.0) -> None:
        self._speed_scale = speed_scale
        self.odometry = Odometry()
        self._clear_robot_fields()

    def _clear_robot_fields(self) -> None:
        self._vel: Optional[Dict[str, float]] = None
        self._imu: Optional[Dict[str, float]] = None
        self._voltage: Optional[float] = None
        self._flag_stop: Any = None
        self._charge: Any = None
        self._health: Any = None
        self._last_cmd_seq: Optional[int] = None

    def clear_robot(self) -> None:
        """The robot link dropped: forget its telemetry (the pose is kept)."""
        self._clear_robot_fields()
        self.odometry.forget_time()

    def reset_odometry(self) -> None:
        self.odometry.reset()

    def on_robot_state(self, msg: Dict[str, Any]) -> None:
        """Take one robot `state` message (PROTO-2)."""
        raw_vel = _finite_dict(msg.get("vel"), ("vx", "vy", "wz"))
        self._vel = None
        if raw_vel is not None:
            scaled = {key: value * self._speed_scale for key, value in raw_vel.items()}
            if all(math.isfinite(value) for value in scaled.values()):  # a huge value overflows when scaled
                self._vel = scaled
        t_ns = msg.get("t_mono_ns")
        if self._vel is not None and isinstance(t_ns, int) and not isinstance(t_ns, bool):
            self.odometry.update(t_ns, self._vel["vx"], self._vel["vy"], self._vel["wz"])
        self._imu = _finite_dict(msg.get("imu"), _IMU_KEYS)
        voltage = msg.get("voltage")
        self._voltage = float(voltage) if _finite(voltage) else None
        flag_stop = msg.get("flag_stop")
        valid_flag = isinstance(flag_stop, (bool, int)) and abs(flag_stop) <= _MAX_INT
        self._flag_stop = flag_stop if valid_flag else None
        self._charge = _clean_dict(msg.get("charge"))
        self._health = _clean_dict(msg.get("health"))
        seq = msg.get("last_cmd_seq")
        valid_seq = isinstance(seq, int) and not isinstance(seq, bool)
        self._last_cmd_seq = seq if valid_seq else None

    def build_state(
        self,
        session: Dict[str, Any],
        robot_connected: bool,
        rtt_s: Optional[float] = None,
    ) -> Dict[str, Any]:
        """The web `state` (PROTO-1). `session` is ControlSession.snapshot() (web units)."""
        rtt_ms = round(rtt_s * 1000.0, 1) if rtt_s is not None else None
        return {
            "t": "state",
            "link": {"robot": robot_connected, "rtt_ms": rtt_ms},
            "session": {"armed": session["armed"], "has_driver": session["has_driver"]},
            "vel": dict(self._vel) if self._vel is not None else None,
            "pose": self.odometry.pose(),
            "cmd": dict(session["cmd"]),
            "imu": dict(self._imu) if self._imu is not None else None,
            "voltage": self._voltage,
            "flag_stop": self._flag_stop,
            "charge": self._charge,
            "health": self._health,
            "last_cmd_seq": self._last_cmd_seq,
        }

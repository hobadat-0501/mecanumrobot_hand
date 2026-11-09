"""Telemetry: scale robot velocity to web units, odometry (PHY-7), build the web `state`.

SAF-01: only `vel` is multiplied by CMD_VEL_DIVISOR (the same constant control.py divides by).
IMU and every other field pass through unscaled. Nothing built here carries the factor or a
wire-unit velocity, so the web only ever sees web units.
"""

from __future__ import annotations

import math
from typing import Any, Dict, Optional

from .control import CMD_VEL_DIVISOR

MAX_DT_S = 0.5  # PHY-7: samples further apart than this are not integrated
_NS_PER_S = 1e9
_IMU_KEYS = ("ax", "ay", "az", "gx", "gy", "gz")


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
        self.x += (vx * cos_mid - vy * sin_mid) * dt
        self.y += (vx * sin_mid + vy * cos_mid) * dt
        self.theta = _wrap_angle(self.theta + wz * dt)
        return True

    def pose(self) -> Dict[str, float]:
        return {"x": self.x, "y": self.y, "theta": self.theta}


class Telemetry:
    """Latest robot telemetry in web units plus odometry; builds the PROTO-1 `state`."""

    def __init__(self) -> None:
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
        if raw_vel is None:
            self._vel = None
        else:
            self._vel = {key: value * CMD_VEL_DIVISOR for key, value in raw_vel.items()}
        t_ns = msg.get("t_mono_ns")
        if self._vel is not None and isinstance(t_ns, int) and not isinstance(t_ns, bool):
            self.odometry.update(t_ns, self._vel["vx"], self._vel["vy"], self._vel["wz"])
        self._imu = _finite_dict(msg.get("imu"), _IMU_KEYS)
        voltage = msg.get("voltage")
        self._voltage = float(voltage) if _finite(voltage) else None
        self._flag_stop = msg.get("flag_stop")
        charge = msg.get("charge")
        self._charge = charge if isinstance(charge, dict) else None
        health = msg.get("health")
        self._health = health if isinstance(health, dict) else None
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

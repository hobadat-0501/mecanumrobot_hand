"""Control core: arm state, driving rights, cmd_vel validation, speed calibration, watchdog.

The only place a command is divided by the calibration scale (SAF-01). The scale is the
SPEED_SCALE setting (1.0 = no scaling); the web never sees it.
No speed limit or clamp exists here (SAF-04).
"""

from __future__ import annotations

import hmac
import math
import time
from typing import Any, Callable, Dict, Iterable, Optional, Tuple

WATCHDOG_S = 0.25
MODE_GRACE_S = 1.0

Vec3 = Tuple[float, float, float]


def token_matches(supplied: Any, expected: str) -> bool:
    """Constant-time token compare. Empty expected or non-str supplied never matches."""
    if not isinstance(supplied, str) or not expected:
        return False
    try:
        return hmac.compare_digest(supplied.encode("utf-8"), expected.encode("utf-8"))
    except UnicodeEncodeError:
        return False


def origin_allowed(origin: Any, allowed: Iterable[str]) -> bool:
    """Exact match of the Origin header against the allow-list."""
    return isinstance(origin, str) and origin in tuple(allowed)


def _finite_number(value: Any) -> bool:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def validate_cmd_vel(msg: Any) -> Tuple[int, float, float, float]:
    """Return (seq, vx, vy, wz) from a cmd_vel message or raise ValueError."""
    if not isinstance(msg, dict):
        raise ValueError("cmd_vel must be an object")
    seq = msg.get("seq")
    if isinstance(seq, bool) or not isinstance(seq, int) or seq < 0:
        raise ValueError("seq must be a non-negative integer")
    for key in ("vx", "vy", "wz"):
        if not _finite_number(msg.get(key)):
            raise ValueError(f"{key} must be a finite number")
    return seq, float(msg["vx"]), float(msg["vy"]), float(msg["wz"])


class ControlSession:
    """Arm state, single driving operator, last accepted command and watchdog.

    Return conventions for T06:
    - methods returning bool: True means accepted.
    - `arm(..., False)` accepted, `disconnect(...)` returning True, and `watchdog_tripped()`
      returning True all mean T06 must send a zero cmd_vel to the robot.
    """

    def __init__(
        self,
        operator_token: str,
        allowed_origins: Iterable[str],
        clock: Callable[[], float] = time.monotonic,
        speed_scale: float = 1.0,
    ) -> None:
        self._speed_scale = speed_scale
        self._token = operator_token
        self._origins = tuple(allowed_origins)
        self._clock = clock
        self._armed = False  # SAF-02
        self._clients: set = set()
        self._driver: Optional[str] = None
        self._last_cmd_at: Optional[float] = None
        self._cmd_web: Vec3 = (0.0, 0.0, 0.0)
        self._last_seq: Optional[int] = None
        self._gesture = False  # gesture mode (D-09): only while armed, only the driver sets it
        self._mode_at = 0.0

    @property
    def gesture(self) -> bool:
        return self._gesture

    @property
    def armed(self) -> bool:
        return self._armed

    @property
    def driver(self) -> Optional[str]:
        return self._driver

    def connect(self, client_id: str, origin: Any) -> bool:
        """Register a client as a viewer; False (not registered) if the Origin is rejected."""
        if not origin_allowed(origin, self._origins):
            return False
        self._clients.add(client_id)
        return True

    def role(self, client_id: str) -> Optional[str]:
        if client_id not in self._clients:
            return None
        return "driver" if client_id == self._driver else "viewer"

    def hello(self, client_id: str, token: Any) -> bool:
        """Claim driving rights. False on bad token, unknown client, or another driver holding."""
        if client_id not in self._clients or not token_matches(token, self._token):
            return False
        if self._driver is not None and self._driver != client_id:
            return False
        self._driver = client_id
        return True

    def disconnect(self, client_id: str) -> bool:
        """Remove a client. If it was the driver: disarm, clear command, return True (emit zero)."""
        self._clients.discard(client_id)
        if client_id != self._driver:
            return False
        self._driver = None
        self._disarm()
        return True

    def arm(self, client_id: str, on: Any) -> bool:
        """Only the driver may arm/disarm. `on` must be a bool."""
        if client_id != self._driver or not isinstance(on, bool):
            return False
        if on:
            self._armed = True
            self._last_cmd_at = None
        else:
            self._disarm()
        return True

    def set_mode(self, client_id: str, on: Any) -> bool:
        """Driver turns gesture mode on/off. On needs `armed` (SAF-09); off is always allowed."""
        if client_id != self._driver or not isinstance(on, bool):
            return False
        if on:
            if not self._armed:
                return False
            self._gesture = True
            self._mode_at = self._clock()
        else:
            self._gesture = False
        return True

    def robot_mode_off(self) -> bool:
        """The robot reports manual mode: follow it, after a short grace for the mode message in
        flight. True when the mode was on and is now off."""
        if self._gesture and self._clock() - self._mode_at > MODE_GRACE_S:
            self._gesture = False
            return True
        return False

    def _disarm(self) -> None:
        self._gesture = False
        self._armed = False
        self._last_cmd_at = None
        self._cmd_web = (0.0, 0.0, 0.0)

    def handle_cmd_vel(self, client_id: str, msg: Any) -> Optional[Dict[str, Any]]:
        """Validate a cmd_vel.

        Raises ValueError if invalid. Returns None when not forwarded (disarmed or not the
        driver). Otherwise returns {"seq","vx","vy","wz"} in wire units, divided by the scale (FR-03).
        """
        seq, vx, vy, wz = validate_cmd_vel(msg)
        if not self._armed or client_id != self._driver:
            return None
        if self._gesture and (vx or vy or wz):
            self._gesture = False  # manual driving wins; the robot does the same on its side
        self._last_cmd_at = self._clock()
        self._cmd_web = (vx, vy, wz)
        self._last_seq = seq
        k = self._speed_scale
        return {"seq": seq, "vx": vx / k, "vy": vy / k, "wz": wz / k}

    def watchdog_tripped(self) -> bool:
        """True once when 250 ms passed since the last accepted command (T06 emits zero)."""
        if self._last_cmd_at is None:
            return False
        if self._clock() - self._last_cmd_at < WATCHDOG_S:
            return False
        self._last_cmd_at = None
        self._cmd_web = (0.0, 0.0, 0.0)
        return True

    def snapshot(self) -> Dict[str, Any]:
        """Session part of the state message; web units (the commanded velocity before calibration)."""
        vx, vy, wz = self._cmd_web
        return {
            "armed": self._armed,
            "has_driver": self._driver is not None,
            "mode": "gesture" if self._gesture else "manual",
            "cmd": {"vx": vx, "vy": vy, "wz": wz},
            "last_cmd_seq": self._last_seq,
        }

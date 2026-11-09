"""Control core: arm state, driving rights, cmd_vel validation, 1.89 division, watchdog.

The ONLY place the 1.89 factor is applied to commands is `to_wire_units` (SAF-01).
No speed limit or clamp exists here (SAF-04).
"""

from __future__ import annotations

import hmac
import math
import time
from typing import Any, Callable, Dict, Iterable, Optional, Tuple

# Telemetry (T06) imports this same constant to multiply velocities back.
CMD_VEL_DIVISOR = 1.89
WATCHDOG_S = 0.25

Vec3 = Tuple[float, float, float]


def to_wire_units(vx: float, vy: float, wz: float) -> Vec3:
    """Web units -> wire units. The single place that divides by CMD_VEL_DIVISOR."""
    return (vx / CMD_VEL_DIVISOR, vy / CMD_VEL_DIVISOR, wz / CMD_VEL_DIVISOR)


def token_matches(supplied: Any, expected: str) -> bool:
    """Constant-time token compare. Empty expected or non-str supplied never matches."""
    if not isinstance(supplied, str) or not expected:
        return False
    return hmac.compare_digest(supplied.encode("utf-8"), expected.encode("utf-8"))


def origin_allowed(origin: Any, allowed: Iterable[str]) -> bool:
    """Exact match of the Origin header against the allow-list."""
    return isinstance(origin, str) and origin in tuple(allowed)


def _finite_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


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
    ) -> None:
        self._token = operator_token
        self._origins = tuple(allowed_origins)
        self._clock = clock
        self._armed = False  # SAF-02
        self._clients: set = set()
        self._driver: Optional[str] = None
        self._last_cmd_at: Optional[float] = None
        self._cmd_web: Vec3 = (0.0, 0.0, 0.0)
        self._last_seq: Optional[int] = None

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

    def _disarm(self) -> None:
        self._armed = False
        self._last_cmd_at = None
        self._cmd_web = (0.0, 0.0, 0.0)

    def handle_cmd_vel(self, client_id: str, msg: Any) -> Optional[Dict[str, Any]]:
        """Validate and convert a cmd_vel.

        Raises ValueError if invalid. Returns None when not forwarded (disarmed or not the
        driver). Otherwise returns {"seq","vx","vy","wz"} in wire units (FR-03).
        """
        seq, vx, vy, wz = validate_cmd_vel(msg)
        if not self._armed or client_id != self._driver:
            return None
        self._last_cmd_at = self._clock()
        self._cmd_web = (vx, vy, wz)
        self._last_seq = seq
        wvx, wvy, wwz = to_wire_units(vx, vy, wz)
        return {"seq": seq, "vx": wvx, "vy": wvy, "wz": wwz}

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
        """Session part of the state message; web units only, never wire values or the factor."""
        vx, vy, wz = self._cmd_web
        return {
            "armed": self._armed,
            "has_driver": self._driver is not None,
            "cmd": {"vx": vx, "vy": vy, "wz": wz},
            "last_cmd_seq": self._last_seq,
        }

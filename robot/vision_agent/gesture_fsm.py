"""Vision state machine (VIS-01). Skeleton (T19): the transitions of plan v7 section 4 driven by
abstract observations; the command is ALWAYS zero here. Real GESTURE/FOLLOW commands come in
T24/T26 and will still leave through the robot agent's arbiter and LiDAR gate."""
from __future__ import annotations

from dataclasses import dataclass

STATES = ("OFF", "ENROLL", "LOCKED", "BIND", "BIND-BACK", "GESTURE", "FOLLOW", "HOLD", "ESTOP")
NS = 1_000_000_000

BIND_TIMEOUT_S = 8.0
BIND_BACK_TIMEOUT_S = 10.0
GESTURE_LOST_S = 3.0
FOLLOW_LOST_S = 1.5
HOLD_TIMEOUT_S = 12.0
SESSION_S = 25 * 60
ESTOP_CLEAR_S = 2.0
STATUS_LOST_S = 0.5


@dataclass
class Observation:
    """What the pipeline saw this frame. Defaults mean 'nothing'."""

    face_match: bool = False  # >= 5/8 frames, allowed, anti-spoof ok, one track
    track_id: int | None = None
    in_gesture_zone: bool = False  # 0.9-1.3 m, enough front samples
    other_person_near: bool = False  # someone else < 1.5 m
    open_palm_1s: bool = False
    back_gallery_full: bool = False
    exit_gesture: bool = False
    bound_visible: bool = False
    identity_low: bool = False
    reacquired: bool = False  # stable 10-15 frames
    camera_error: bool = False
    user_disabled: bool = False  # driver's permission revoked or deleted


class GestureFsm:
    def __init__(self) -> None:
        self.state = "OFF"
        self.user: str | None = None
        self._track: int | None = None
        self._entered_ns = 0
        self._session_ns = 0
        self._lost_ns: int | None = None
        self._prev = "GESTURE"
        self._calm_ns: int | None = None

    def _go(self, state: str, now: int) -> None:
        self.state = state
        self._entered_ns = now
        self._lost_ns = None

    def _lock(self, now: int) -> None:
        self.user = None
        self._track = None
        self._go("LOCKED", now)

    def mode_changed(self, on: bool, now_ns: int) -> None:
        """Robot agent reported gesture mode on/off (robot_status.mode)."""
        if on and self.state == "OFF":
            self._session_ns = now_ns
            self._lock(now_ns)
        elif not on and self.state not in ("OFF", "ENROLL"):
            self.user = None
            self._track = None
            self._go("OFF", now_ns)

    def enroll(self, start: bool, now_ns: int) -> bool:
        if start and self.state == "OFF":
            self._go("ENROLL", now_ns)
            return True
        if not start and self.state == "ENROLL":
            self._go("OFF", now_ns)
            return True
        return False

    def step(
        self,
        obs: Observation,
        now_ns: int,
        *,
        status_age_s: float = 0.0,
        flag_stop: bool = False,
        robot_still: bool = True,
        user: str | None = None,
    ) -> str:
        """Advance one frame and return the new state."""
        s = self.state
        if s in ("OFF", "ENROLL"):
            return s
        fault = status_age_s > STATUS_LOST_S or flag_stop or obs.camera_error
        if s == "ESTOP":
            if fault or not robot_still:
                self._calm_ns = None
            else:
                self._calm_ns = self._calm_ns or now_ns
                if now_ns - self._calm_ns >= ESTOP_CLEAR_S * NS:
                    self._calm_ns = None
                    self._lock(now_ns)
            return self.state
        if fault:
            self._calm_ns = None
            self._go("ESTOP", now_ns)
            return self.state
        if obs.user_disabled or now_ns - self._session_ns > SESSION_S * NS:
            self._lock(now_ns)
            return self.state
        age = (now_ns - self._entered_ns) / NS
        if s == "LOCKED":
            if obs.face_match and obs.track_id is not None:
                self.user, self._track = user, obs.track_id
                self._go("BIND", now_ns)
        elif s == "BIND":
            if age > BIND_TIMEOUT_S or obs.track_id != self._track or obs.other_person_near:
                self._lock(now_ns)
            elif obs.in_gesture_zone:
                self._go("GESTURE", now_ns)
        elif s == "GESTURE":
            if obs.bound_visible:
                self._lost_ns = None
                if obs.open_palm_1s:
                    self._go("BIND-BACK", now_ns)
            else:
                self._lost_ns = self._lost_ns or now_ns
                if now_ns - self._lost_ns > GESTURE_LOST_S * NS:
                    self._prev = "GESTURE"
                    self._go("HOLD", now_ns)
        elif s == "BIND-BACK":
            if age > BIND_BACK_TIMEOUT_S or obs.track_id != self._track:
                self._go("GESTURE", now_ns)
            elif obs.back_gallery_full:
                self._go("FOLLOW", now_ns)
        elif s == "FOLLOW":
            if obs.exit_gesture:
                self._go("GESTURE", now_ns)
            elif obs.identity_low or obs.track_id != self._track:
                self._prev = "FOLLOW"
                self._go("HOLD", now_ns)
            elif not obs.bound_visible:
                self._lost_ns = self._lost_ns or now_ns
                if now_ns - self._lost_ns > FOLLOW_LOST_S * NS:
                    self._prev = "FOLLOW"
                    self._go("HOLD", now_ns)
            else:
                self._lost_ns = None
        elif s == "HOLD":
            if obs.reacquired:
                self._go(self._prev, now_ns)
            elif age > HOLD_TIMEOUT_S:
                self._lock(now_ns)
        return self.state

    def command(self) -> tuple[float, float, float]:
        """Skeleton: always zero in every state (T19)."""
        return (0.0, 0.0, 0.0)

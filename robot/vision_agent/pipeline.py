"""Frame source and the scripted simulator (NFR-08). No camera or GPU is needed with simulate."""
from __future__ import annotations

import base64
import time
from dataclasses import dataclass, field

from .gesture_fsm import NS, GestureFsm, Observation

# 16x16 solid-colour JPEG: stands in for the camera frame in simulation.
SIM_JPEG = base64.b64decode(
    "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAARCAAQABADASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwDIooor68+VP//Z"
)

# (seconds since mode on, Observation fields): LOCKED -> BIND -> GESTURE -> BIND-BACK -> FOLLOW -> HOLD.
SCRIPT: tuple[tuple[float, dict], ...] = (
    (0.0, {}),
    (1.0, {"face_match": True, "track_id": 1}),
    (2.0, {"track_id": 1, "in_gesture_zone": True, "bound_visible": True}),
    (4.0, {"track_id": 1, "bound_visible": True, "open_palm_1s": True}),
    (5.0, {"track_id": 1, "bound_visible": True, "back_gallery_full": True}),
    (8.0, {"track_id": 1, "bound_visible": False}),
    (11.0, {"track_id": 1, "bound_visible": True, "reacquired": True}),
)


@dataclass
class Pipeline:
    simulate: bool = True
    fsm: GestureFsm = field(default_factory=GestureFsm)
    _t0: int | None = None
    frames: int = 0

    def mode_changed(self, on: bool, now_ns: int) -> None:
        self._t0 = now_ns if on else None
        self.fsm.mode_changed(on, now_ns)

    def _observation(self, now_ns: int) -> Observation:
        if not self.simulate or self._t0 is None:
            return Observation()
        t = (now_ns - self._t0) / NS
        fields: dict = {}
        for at, values in SCRIPT:
            if t >= at:
                fields = values
        return Observation(**fields)

    def frame(self, now_ns: int | None = None, **status) -> bytes:
        """One tick: advance the FSM and return the JPEG for the video stream."""
        now = time.monotonic_ns() if now_ns is None else now_ns
        self.fsm.step(self._observation(now), now, **status)
        self.frames += 1
        return SIM_JPEG

    def vision_state(self, mode_on: bool, fps: float = 0.0) -> dict:
        """PROTO-3 vision_state. Carries no velocity (the command never leaves via the app)."""
        return {
            "t": "vision_state", "mode": mode_on, "state": self.fsm.state, "user": self.fsm.user,
            "gesture": None, "cmd": {"active": False}, "guide": None, "fps": fps,
            "temps": {}, "events": [],
        }

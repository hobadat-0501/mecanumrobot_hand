"""Manual keyboard commands with a bounded command lifetime."""
from __future__ import annotations

import math
import threading
import time
from typing import Any

ZERO = (0.0, 0.0, 0.0)
DIRECTIONS = {
    "w": (1, 0, 0), "s": (-1, 0, 0),
    "a": (0, 1, 0), "d": (0, -1, 0),
    "q": (0, 0, 1), "e": (0, 0, -1),
    "up": (1, 0, 0), "down": (-1, 0, 0),
    "left": (0, 1, 0), "right": (0, -1, 0),
}


class KeyboardDrive:
    def __init__(
        self, source: Any, *, speed_mps: float = 0.05,
        yaw_radps: float = 0.25, timeout_s: float = 0.25,
        telemetry_timeout_s: float = 0.5, enable_motion: bool = False,
    ) -> None:
        for name, value in (("speed", speed_mps), ("yaw rate", yaw_radps),
                            ("key timeout", timeout_s), ("telemetry timeout", telemetry_timeout_s)):
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be positive and finite")
        if speed_mps > 0.2 or yaw_radps > 1.0:
            raise ValueError("manual speed limits are 0.2 m/s and 1 rad/s")
        if timeout_s > 0.5 or telemetry_timeout_s > 1.0:
            raise ValueError("manual timeouts must not exceed 0.5 s (key) and 1 s (telemetry)")
        self.source = source
        self.speed = speed_mps
        self.yaw = yaw_radps
        self.timeout = timeout_s
        self.telemetry_timeout = telemetry_timeout_s
        self.motion_allowed = enable_motion
        self.armed = enable_motion
        self._command = ZERO
        self._deadline = 0.0
        self._lock = threading.RLock()
        self.stop_event = threading.Event()
        self.error: Exception | None = None
        self._thread: threading.Thread | None = None

    def press(self, key: str, *, now: float | None = None) -> None:
        now = time.monotonic() if now is None else now
        with self._lock:
            if key == "x":
                self.armed = False
            elif key == "r" and self.motion_allowed:
                self.armed = True
            direction = DIRECTIONS.get(key)
            if direction is not None and self.armed:
                self._command = (direction[0] * self.speed, direction[1] * self.speed,
                                 direction[2] * self.yaw)
                self._deadline = now + self.timeout
            else:
                self._command = ZERO
                self._deadline = 0.0

    def tick(self, *, now: float | None = None, wall_ns: int | None = None) -> tuple[float, float, float]:
        now = time.monotonic() if now is None else now
        wall_ns = time.time_ns() if wall_ns is None else wall_ns
        with self._lock:
            sample = self.source.latest
            age_s = (wall_ns - sample.t_ns) / 1e9 if sample is not None else math.inf
            fresh = 0 <= age_s <= self.telemetry_timeout
            if not self.armed or now >= self._deadline or not fresh or sample.flag_stop:
                # Discard the command so recovered telemetry cannot restart old motion.
                self._command = ZERO
                self._deadline = 0.0
            self.source.send_velocity(*self._command)
            return self._command

    def start(self) -> None:
        if self._thread is not None:
            raise RuntimeError("keyboard drive is already started")
        self.source.send_velocity(*ZERO)
        self.stop_event.clear()
        self._thread = threading.Thread(target=self._run, name="keyboard-writer", daemon=True)
        self._thread.start()

    def _run(self) -> None:
        try:
            while not self.stop_event.is_set():
                self.tick()
                self.stop_event.wait(0.05)
        except Exception as error:
            self.error = error
            self.stop_event.set()
        finally:
            try:
                self.source.send_velocity(*ZERO)
            except Exception as error:
                self.error = self.error or error

    def stop(self) -> None:
        self.stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            if self._thread.is_alive():
                raise RuntimeError("keyboard writer did not stop; close the serial transport")
            self._thread = None
        self.source.send_velocity(*ZERO)

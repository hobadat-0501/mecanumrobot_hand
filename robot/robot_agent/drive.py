"""cmd_vel writer: a one-slot mailbox plus a loop that feeds the STM32 safe velocities.

Velocities are (vx, vy, wz) in STM32 wire units (m/s, m/s, rad/s). There is no speed limit
here by design (SAF-04); only non-finite values and values that do not fit the STM32 int16
frame are rejected. All ages use the monotonic clock (time.monotonic_ns).
"""
from __future__ import annotations

import math
import threading
import time
from dataclasses import dataclass
from typing import Any

from .hardware import encode_stm32_velocity_command

ZERO = (0.0, 0.0, 0.0)
_NS = 1_000_000_000


@dataclass(frozen=True)
class WriterHealth:
    running: bool  # writer thread is alive
    healthy: bool  # the most recent write attempt succeeded
    error_count: int  # write/telemetry-read errors since construction
    last_error: str | None  # "ExceptionType: message" of the latest error
    rejected_count: int  # set_cmd_vel calls rejected (non-finite or outside int16)
    last_write_ns: int | None  # monotonic time of the latest successful write


class CmdVelWriter:
    def __init__(
        self,
        source: Any,
        *,
        motion_enabled: bool = False,
        deadman_s: float = 0.25,
        telemetry_timeout_s: float = 0.5,
        period_s: float = 0.05,
        retry_s: float = 0.2,
        join_timeout_s: float = 2.0,
    ) -> None:
        for name, value in (
            ("deadman_s", deadman_s),
            ("telemetry_timeout_s", telemetry_timeout_s),
            ("period_s", period_s),
            ("retry_s", retry_s),
            ("join_timeout_s", join_timeout_s),
        ):
            if not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be positive and finite")
        self.source = source
        self.motion_enabled = bool(motion_enabled)
        self.period_s = float(period_s)
        self.retry_s = float(retry_s)
        self.join_timeout_s = float(join_timeout_s)
        self._deadman_ns = int(round(deadman_s * _NS))
        self._telemetry_ns = int(round(telemetry_timeout_s * _NS))
        # Mailbox and health state. _lock is held only for short in-memory updates and is
        # never held while writing to the source.
        self._lock = threading.Lock()
        self._cmd: tuple[float, float, float] | None = None
        self._cmd_ns = 0
        self._seq = 0
        self._healthy = False
        self._error_count = 0
        self._last_error: str | None = None
        self._rejected = 0
        self._last_write_ns: int | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    # ---- mailbox (never touches the serial port) ----

    @staticmethod
    def _fits_frame(values: tuple[Any, Any, Any]) -> bool:
        # Reuse the encoder so the accepted range is exactly what the STM32 frame can carry
        # (finite, and round(v * 1000) within int16).
        try:
            encode_stm32_velocity_command(*values)
        except (ValueError, TypeError, OverflowError):
            return False
        return True

    def set_cmd_vel(self, vx: float, vy: float, wz: float, now_ns: int | None = None) -> bool:
        """Store the latest command. Returns False when rejected (the mailbox is then emptied)."""
        accepted = self._fits_frame((vx, vy, wz))
        with self._lock:
            stamp = time.monotonic_ns() if now_ns is None else now_ns
            self._seq += 1
            if accepted:
                self._cmd = (float(vx), float(vy), float(wz))
                self._cmd_ns = stamp
            else:
                self._cmd = None
                self._rejected += 1
        return accepted

    def clear(self) -> None:
        """Discard the stored command (link loss). The next write is zero."""
        with self._lock:
            self._seq += 1
            self._cmd = None

    def health(self) -> WriterHealth:
        thread = self._thread
        with self._lock:
            return WriterHealth(
                running=thread is not None and thread.is_alive(),
                healthy=self._healthy,
                error_count=self._error_count,
                last_error=self._last_error,
                rejected_count=self._rejected,
                last_write_ns=self._last_write_ns,
            )

    def _record_error(self, error: BaseException) -> None:
        with self._lock:
            self._healthy = False
            self._error_count += 1
            self._last_error = f"{type(error).__name__}: {error}"

    # ---- writing ----

    def _usable(self, cmd_ns: int, sample: Any, now_ns: int) -> bool:
        if not self.motion_enabled or sample is None or sample.flag_stop:
            return False
        if not 0 <= now_ns - sample.t_ns <= self._telemetry_ns:
            return False
        return 0 <= now_ns - cmd_ns <= self._deadman_ns

    def tick(self, now_ns: int | None = None) -> tuple[float, float, float] | None:
        """Write one velocity. Returns what was written, or None when the write failed."""
        try:
            sample = self.source.latest
        except Exception as error:
            self._record_error(error)
            sample = None
        with self._lock:
            now = time.monotonic_ns() if now_ns is None else now_ns
            seq = self._seq
            command = ZERO
            if self._cmd is not None:
                if self._usable(self._cmd_ns, sample, now):
                    command = self._cmd
                else:
                    # Expired, stale telemetry, stop flag or motion off: discard it for good.
                    self._cmd = None
        try:
            self.source.send_velocity(*command)  # outside the lock
        except Exception as error:
            with self._lock:
                if self._seq == seq:  # keep a command that arrived during the failed write
                    self._cmd = None
            self._record_error(error)
            return None
        with self._lock:
            self._healthy = True
            self._last_write_ns = now
        return command

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                ok = self.tick() is not None
            except Exception as error:
                self._record_error(error)
                ok = False
            self._stop.wait(self.period_s if ok else self.retry_s)

    def start(self) -> None:
        if self._thread is not None:
            raise RuntimeError("cmd_vel writer is already started")
        self.clear()
        self._stop.clear()
        thread = threading.Thread(target=self._run, name="cmd-vel-writer", daemon=True)
        self._thread = thread
        thread.start()

    def stop(self) -> bool:
        """Stop the loop and try a final zero. Returns True only if both succeeded."""
        self._stop.set()
        self.clear()
        thread = self._thread
        if thread is not None:
            thread.join(timeout=self.join_timeout_s)
            if thread.is_alive():
                self._record_error(RuntimeError("cmd_vel writer thread did not stop in time"))
                return False
            self._thread = None
        try:
            self.source.send_velocity(*ZERO)
        except Exception as error:
            self._record_error(error)
            return False
        return True

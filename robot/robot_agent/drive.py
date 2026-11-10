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


# ---------------------------------------------------------------------------------------------
# Gesture mode (v7): ModeGuard, LiDAR gate and CmdArbiter. Everything here sits in front of
# CmdVelWriter.set_cmd_vel; the writer's own layers (ROBOT_MOTION_ENABLED, deadman, stale
# telemetry, flag_stop, int16 range) stay in force for every source.
# ---------------------------------------------------------------------------------------------

VISION_RUN_STATES = frozenset(("GESTURE", "FOLLOW", "HOLD"))


def _is_zero(vx: Any, vy: Any, wz: Any) -> bool:
    # NaN != 0 is True, so a non-finite command counts as "not zero" and reaches the writer,
    # which rejects it (SAF-04).
    return vx == 0 and vy == 0 and wz == 0


class LidarGate:
    """Blocks (never clamps) a vision command when an obstacle lies in the swept body area.

    The body is the footprint rectangle centred on the robot. LiDAR points are moved into the
    robot-centre frame first (the LiDAR is not at the centre, so the safe area around it is not
    symmetric). The area swept over `t_check_s` at the commanded (vx, vy, wz), plus a margin, is
    tested; any point inside, a stale scan or no scan means blocked (SAF-11). Zero always passes.
    """

    def __init__(
        self,
        *,
        footprint_x_m: float = 0.40,
        footprint_y_m: float = 0.40,
        lidar_x_m: float = 0.10,
        lidar_y_m: float = 0.0,
        t_check_s: float = 0.5,
        margin_m: float = 0.15,
        scan_max_age_s: float = 0.3,
    ) -> None:
        self._half_x = footprint_x_m / 2.0
        self._half_y = footprint_y_m / 2.0
        self._lidar_x = lidar_x_m
        self._lidar_y = lidar_y_m
        self._t_check = t_check_s
        self._margin = margin_m
        self.max_age_ns = int(round(scan_max_age_s * _NS))

    def _points(self, scan: Any) -> list[tuple[float, float, float]]:
        """(x_robot, y_robot, lidar_range) of every valid point."""
        out = []
        for point in scan.points:
            angle, rng = point.angle_rad, point.range_m
            if not (math.isfinite(angle) and math.isfinite(rng)) or rng <= 0.0:
                continue
            out.append(
                (
                    rng * math.cos(angle) + self._lidar_x,
                    rng * math.sin(angle) + self._lidar_y,
                    rng,
                )
            )
        return out

    def self_check(self, scan: Any) -> int:
        """Number of points inside the bare footprint: non-zero means something is mounted on the
        robot or the LiDAR is displaced (reported, not silently ignored)."""
        return sum(
            1
            for x, y, _ in self._points(scan)
            if abs(x) <= self._half_x and abs(y) <= self._half_y
        )

    def check(
        self, vx: float, vy: float, wz: float, scan: Any, now_ns: int
    ) -> tuple[bool, float | None]:
        """Returns (blocked, min_m); min_m is the nearest blocking point's LiDAR range."""
        if _is_zero(vx, vy, wz):
            return False, None
        if scan is None or not 0 <= now_ns - scan.t_ns <= self.max_age_ns:
            return True, None
        if not all(math.isfinite(v) for v in (vx, vy, wz)):
            return True, None
        t = self._t_check
        reach = math.hypot(vx, vy) * t + abs(wz) * t * math.hypot(self._half_x, self._half_y)
        steps = max(1, min(200, math.ceil(reach / 0.05)))
        poses = []
        for k in range(steps + 1):
            tk = t * k / steps
            theta = wz * tk
            poses.append((vx * tk, vy * tk, math.cos(theta), math.sin(theta)))
        hx = self._half_x + self._margin
        hy = self._half_y + self._margin
        nearest: float | None = None
        for x, y, rng in self._points(scan):
            for dx, dy, c, s in poses:
                # Point in the body frame at time tk: R(-theta) * (p - d)
                bx = c * (x - dx) + s * (y - dy)
                by = -s * (x - dx) + c * (y - dy)
                if abs(bx) <= hx and abs(by) <= hy:
                    if nearest is None or rng < nearest:
                        nearest = rng
                    break
        return nearest is not None, nearest


class ModeGuard:
    """Gesture mode flag plus heartbeat supervision (SAF-09). Not thread-safe by itself."""

    def __init__(self, *, block_s: float = 0.5, off_s: float = 3.0) -> None:
        self._block_ns = int(round(block_s * _NS))
        self._off_ns = int(round(off_s * _NS))
        self.on = False
        self.reason: str | None = None  # why the mode last went off
        self._last_hb_ns = 0

    def enable(self, now_ns: int) -> None:
        self.on = True
        self.reason = None
        self._last_hb_ns = now_ns

    def disable(self, reason: str) -> None:
        self.on = False
        self.reason = reason

    def heartbeat(self, now_ns: int) -> None:
        if self.on:
            self._last_hb_ns = now_ns

    def hb_age_ns(self, now_ns: int) -> int:
        return now_ns - self._last_hb_ns

    def blocked(self, now_ns: int) -> bool:
        return self.on and self.hb_age_ns(now_ns) > self._block_ns

    def update(self, now_ns: int) -> bool:
        """Turn the mode off once the heartbeat is lost for too long. Returns True if it did."""
        if self.on and self.hb_age_ns(now_ns) > self._off_ns:
            self.disable("heartbeat")
            return True
        return False


class CmdArbiter:
    """Decides which source feeds the writer: app server (manual) or vision (gesture mode).

    It exposes the same entry points the robot server used on the writer (set_cmd_vel, clear,
    health), so the server can talk to it unchanged. `step()` must be called periodically (20 Hz);
    it supervises the heartbeat and forwards the newest vision command through the LiDAR gate.
    """

    SOURCE_HOLD_NS = 250_000_000  # how long a source label stays after its last command

    def __init__(
        self,
        writer: Any,
        *,
        lidar: Any = None,
        gate: LidarGate | None = None,
        vision_enabled: bool = False,
        vision_max_age_s: float = 0.1,
        guard: ModeGuard | None = None,
    ) -> None:
        self.writer = writer
        self._lidar = lidar
        self.gate = gate if gate is not None else LidarGate()
        self.vision_enabled = bool(vision_enabled)
        self._vision_max_age_ns = int(round(vision_max_age_s * _NS))
        self.guard = guard if guard is not None else ModeGuard()
        # (seq, t_mono_ns, vx, vy, wz, state) of the newest accepted vision command
        self._vision: tuple[int, int, float, float, float, str] | None = None
        self._last_vision_seq: int | None = None
        self._gate_blocked = False
        self._gate_min_m: float | None = None
        self._src = "none"
        self._src_ns = 0
        self._wrote_vision = False

    # ---- writer-compatible surface (used by RobotServer for the app source) ----

    def set_cmd_vel(self, vx: float, vy: float, wz: float, now_ns: int | None = None) -> bool:
        if self.guard.on:
            if _is_zero(vx, vy, wz):
                return True  # not a manual intent: ignored while gesture mode runs
            self.set_mode(False, reason="manual")  # manual driving always wins
        accepted = self.writer.set_cmd_vel(vx, vy, wz, now_ns)
        self._mark("app", now_ns)
        return accepted

    def clear(self) -> None:
        """Link lost or replaced: drop gesture mode and the stored command."""
        self.set_mode(False, reason="link")
        self.writer.clear()

    def health(self) -> WriterHealth:
        return self.writer.health()

    # ---- session commands (PROTO-2 mode / hb) ----

    def set_mode(self, on: bool, reason: str = "web", now_ns: int | None = None) -> None:
        now = time.monotonic_ns() if now_ns is None else now_ns
        self._vision = None
        self._last_vision_seq = None
        self._gate_blocked = False
        self._gate_min_m = None
        if on:
            self.guard.enable(now)
            return
        was_on = self.guard.on
        self.guard.disable(reason)
        self._wrote_vision = False
        if was_on:
            self.writer.clear()

    def heartbeat(self, now_ns: int | None = None) -> None:
        self.guard.heartbeat(time.monotonic_ns() if now_ns is None else now_ns)

    # ---- vision input (PROTO-4) ----

    def submit_vision(
        self, seq: int, t_mono_ns: int, vx: float, vy: float, wz: float, state: str
    ) -> bool:
        """Store the newest vision command. Returns False when it is dropped outright."""
        if not self.guard.on:
            return False
        if self._last_vision_seq is not None and seq <= self._last_vision_seq:
            return False  # seq went backwards or repeated
        self._last_vision_seq = seq
        self._vision = (seq, t_mono_ns, vx, vy, wz, state)
        return True

    # ---- periodic ----

    def step(self, now_ns: int | None = None) -> tuple[float, float, float] | None:
        """Supervise the heartbeat and feed vision to the writer. Returns what was forwarded."""
        now = time.monotonic_ns() if now_ns is None else now_ns
        if self.guard.update(now):
            self.writer.clear()
            self._vision = None
            self._wrote_vision = False
        if not self.guard.on:
            return None
        forwarded = self._forward(now)
        if forwarded is None and self._wrote_vision:
            self.writer.clear()  # was driving from vision, now blocked or invalid: zero at once
        self._wrote_vision = forwarded is not None
        return forwarded

    def _forward(self, now: int) -> tuple[float, float, float] | None:
        if not self.vision_enabled or self.guard.blocked(now) or self._vision is None:
            return None
        _, t_ns, vx, vy, wz, state = self._vision
        if state not in VISION_RUN_STATES or not 0 <= now - t_ns <= self._vision_max_age_ns:
            return None
        scan = self._lidar.latest if self._lidar is not None else None
        blocked, min_m = self.gate.check(vx, vy, wz, scan, now)
        self._gate_blocked, self._gate_min_m = blocked, min_m
        if blocked:
            vx = vy = wz = 0.0
        self.writer.set_cmd_vel(vx, vy, wz, now)
        self._mark("vision", now)
        return (vx, vy, wz)

    # ---- reporting ----

    def _mark(self, src: str, now_ns: int | None) -> None:
        self._src = src
        self._src_ns = time.monotonic_ns() if now_ns is None else now_ns

    def report(self, now_ns: int | None = None) -> dict[str, Any]:
        """Fields the robot server adds to `state` (PROTO-2, v7)."""
        now = time.monotonic_ns() if now_ns is None else now_ns
        age_ms = None
        if self._vision is not None:
            age_ms = max(0, (now - self._vision[1]) // 1_000_000)
        recent = 0 <= now - self._src_ns <= self.SOURCE_HOLD_NS
        return {
            "mode": "gesture" if self.guard.on else "manual",
            "src": self._src if recent else "none",
            "vision": {
                "link": age_ms is not None and age_ms <= 500,
                "blocked": self.guard.blocked(now),
                "last_cmd_age_ms": age_ms,
            },
            "lidar_gate": {"blocked": self._gate_blocked, "min_m": self._gate_min_m},
        }

    def robot_status(self, stm_sample: Any, now_ns: int | None = None) -> dict[str, Any]:
        """Payload for PROTO-4 `robot_status` (sent to the vision agent at 20 Hz)."""
        now = time.monotonic_ns() if now_ns is None else now_ns
        scan = self._lidar.latest if self._lidar is not None else None
        return {
            "t": "robot_status",
            "t_mono_ns": now,
            "mode": self.guard.on,
            "blocked": self.guard.blocked(now),
            "flag_stop": bool(stm_sample.flag_stop) if stm_sample is not None else True,
            "gz": float(stm_sample.gyro_z_radps) if stm_sample is not None else 0.0,
            "lidar_ok": scan is not None and 0 <= now - scan.t_ns <= self.gate.max_age_ns,
        }

"""Simulated STM32 and LiDAR for ROBOT_SIMULATE=true (NFR-06).

Drop-in replacements for the real sources: same attributes and methods that the writer, the
server and the supervisor use. Both are computed lazily from a clock, so there are no threads.
No hardware libraries are imported.
"""
from __future__ import annotations

import math
import threading
import time
from collections.abc import Callable

from .hardware import (
    LidarPoint,
    LidarScan,
    Stm32AuxTelemetry,
    Stm32Telemetry,
    encode_stm32_velocity_command,
)


class SimulatedStm32:
    """First-order velocity response toward the last command, reported in wire units."""

    def __init__(
        self,
        *,
        tau_s: float = 0.1,
        voltage_v: float = 12.0,
        clock_ns: Callable[[], int] = time.monotonic_ns,
    ) -> None:
        if not math.isfinite(tau_s) or tau_s <= 0.0:
            raise ValueError("tau_s must be positive and finite")
        self.tau_s = tau_s
        self.voltage_v = voltage_v
        self.errors = 0
        self.last_command: tuple[int, float, float, float] | None = None
        self._clock = clock_ns
        self._lock = threading.Lock()
        self._started = False
        self._t_ns = 0
        self._velocity = (0.0, 0.0, 0.0)
        self._target = (0.0, 0.0, 0.0)

    def _advance(self) -> None:
        # Caller holds the lock. The sample time never goes backwards.
        now = max(self._clock(), self._t_ns)
        dt = (now - self._t_ns) / 1e9
        if dt > 0.0:
            keep = math.exp(-dt / self.tau_s)
            self._velocity = tuple(
                goal + (value - goal) * keep for value, goal in zip(self._velocity, self._target)
            )
        self._t_ns = now

    def start(self) -> None:
        with self._lock:
            self._started = True
            self._t_ns = self._clock()
            self._velocity = (0.0, 0.0, 0.0)
            self._target = (0.0, 0.0, 0.0)
            self.errors = 0

    def stop(self) -> None:
        with self._lock:
            self._started = False
            self._velocity = (0.0, 0.0, 0.0)
            self._target = (0.0, 0.0, 0.0)

    def send_velocity(self, vx_mps: float, vy_mps: float, wz_radps: float) -> None:
        # Same validation as the real frame encoder (finite and within int16 millimetres).
        encode_stm32_velocity_command(vx_mps, vy_mps, wz_radps)
        with self._lock:
            if not self._started:
                raise RuntimeError("simulated STM32 is not started")
            self._advance()
            wire = (vx_mps, vy_mps, wz_radps)
            self._target = tuple(round(float(v) * 1000.0) / 1000.0 for v in wire)
            self.last_command = (self._t_ns, float(vx_mps), float(vy_mps), float(wz_radps))

    @property
    def latest(self) -> Stm32Telemetry | None:
        with self._lock:
            if not self._started:
                return None
            self._advance()
            vx, vy, wz = (round(v * 1000.0) / 1000.0 for v in self._velocity)
            return Stm32Telemetry(
                t_ns=self._t_ns,
                flag_stop=0,
                vx_mps=vx,
                vy_mps=vy,
                wz_radps=wz,
                accel_x_mps2=0.0,
                accel_y_mps2=0.0,
                accel_z_mps2=9.81,
                gyro_x_radps=0.0,
                gyro_y_radps=0.0,
                gyro_z_radps=wz,
                voltage_v=self.voltage_v,
            )

    @property
    def latest_aux(self) -> Stm32AuxTelemetry | None:
        with self._lock:
            if not self._started:
                return None
            self._advance()
            return Stm32AuxTelemetry(
                t_ns=self._t_ns, charging_current_a=0.0, red=0, charging=False, charge_set_state=0
            )


class SimulatedLidar:
    """A fake 360 point scan, one new scan every period_s (default 10 Hz)."""

    def __init__(
        self,
        *,
        period_s: float = 0.1,
        clock_ns: Callable[[], int] = time.monotonic_ns,
    ) -> None:
        if not math.isfinite(period_s) or period_s <= 0.0:
            raise ValueError("period_s must be positive and finite")
        self.error: Exception | None = None
        self._period_ns = max(1, int(round(period_s * 1e9)))
        self._clock = clock_ns
        self._lock = threading.Lock()
        self._started = False
        self._t0_ns = 0
        self._scan: LidarScan | None = None

    def start(self) -> None:
        with self._lock:
            self._started = True
            self._t0_ns = self._clock()
            self._scan = None
            self.error = None

    def stop(self) -> None:
        with self._lock:
            self._started = False
            self._scan = None

    @property
    def scan_rate_hz(self) -> float:
        return 1e9 / self._period_ns if self._started else 0.0

    @property
    def latest(self) -> LidarScan | None:
        with self._lock:
            if not self._started:
                return None
            index = (self._clock() - self._t0_ns) // self._period_ns
            if index < 1:
                return None
            t_ns = self._t0_ns + index * self._period_ns
            if self._scan is None or self._scan.t_ns != t_ns:
                wobble = 0.05 * math.sin(index / 5.0)
                points = tuple(
                    LidarPoint(
                        t_ns,
                        math.radians(degree),
                        2.0 + 0.5 * math.sin(math.radians(2 * degree)) + wobble,
                        100,
                        0,
                    )
                    for degree in range(360)
                )
                self._scan = LidarScan(t_ns, points)
            return self._scan

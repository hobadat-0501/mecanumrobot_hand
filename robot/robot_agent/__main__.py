"""Robot agent entry point: python -m robot_agent.

Starts the STM32 and LiDAR sources (real, or simulated with ROBOT_SIMULATE=true), the cmd_vel
writer and the WebSocket server. Each device is supervised on its own: a device that fails to
start, or later stops producing data, is reported in health and retried with back-off, without
affecting the writer, the other device or the server. The camera is never started (D-07).
"""
from __future__ import annotations

import asyncio
import logging
import signal
import sys
import time
from collections.abc import Callable
from typing import Any

from . import hardware
from .config import Config, ConfigError, load_config
from .drive import CmdVelWriter
from .server import RobotServer
from .sim import SimulatedLidar, SimulatedStm32

log = logging.getLogger("robot_agent")


class SupervisedDevice:
    """Starts a source from a factory, watches it for fresh data, restarts it with back-off.

    Also acts as the source itself (latest, latest_aux, send_velocity) so the writer and the
    server keep working across restarts: while there is no running source, latest is None and
    send_velocity raises, which the writer records and retries.
    """

    def __init__(
        self,
        name: str,
        factory: Callable[[], Any],
        probe: Callable[[Any], int | None],
        *,
        stale_s: float,
        backoff_s: float = 0.5,
        max_backoff_s: float = 5.0,
        poll_s: float = 0.1,
    ) -> None:
        self.name = name
        self._factory = factory
        self._probe = probe  # returns a stamp that changes whenever the source produced data
        self._stale_s = stale_s
        self._backoff_s = backoff_s
        self._max_backoff_s = max_backoff_s
        self._poll_s = poll_s
        self._source: Any = None
        self._state = "starting"
        self._error: str | None = None
        self.restarts = 0

    # ---- source proxy ----

    @property
    def latest(self) -> Any:
        source = self._source
        return source.latest if source is not None else None

    @property
    def latest_aux(self) -> Any:
        source = self._source
        return getattr(source, "latest_aux", None) if source is not None else None

    def send_velocity(self, vx: float, vy: float, wz: float) -> None:
        source = self._source
        if source is None:
            raise RuntimeError(f"{self.name} is not running")
        source.send_velocity(vx, vy, wz)

    def health(self) -> dict[str, Any]:
        return {
            "ok": self._state == "ok",
            "state": self._state,
            "error": self._error,
            "restarts": self.restarts,
        }

    # ---- supervision ----

    @staticmethod
    def _stop_now(source: Any) -> None:
        try:
            source.stop()
        except Exception:
            log.exception("stopping a device source failed")

    async def _watch(self, source: Any) -> tuple[bool, str]:
        """Wait until the source fails or goes quiet. Returns (produced_data, reason)."""
        stamp = None
        produced = False
        last_progress = time.monotonic()
        while True:
            await asyncio.sleep(self._poll_s)
            error = getattr(source, "error", None)
            if error is not None:
                return produced, f"{type(error).__name__}: {error}"
            try:
                current = self._probe(source)
            except Exception as exc:
                return produced, f"{type(exc).__name__}: {exc}"
            now = time.monotonic()
            if current is not None and current != stamp:
                stamp = current
                produced = True
                last_progress = now
                self._state = "ok"
                self._error = None
            elif now - last_progress > self._stale_s:
                return produced, f"no data for more than {self._stale_s:g} s"

    async def run(self) -> None:
        delay = self._backoff_s
        source = None
        try:
            while True:
                produced = False
                try:
                    self._state = "starting"
                    source = self._factory()
                    await asyncio.to_thread(source.start)
                    self._source = source
                    produced, reason = await self._watch(source)
                except Exception as exc:
                    reason = f"{type(exc).__name__}: {exc}"
                self._source = None
                if source is not None:
                    await asyncio.to_thread(self._stop_now, source)
                    source = None
                self._state = "failed"
                self._error = reason
                self.restarts += 1
                log.warning("%s: %s; retrying in %.1f s", self.name, reason, delay)
                delay = self._backoff_s if produced else min(delay * 2, self._max_backoff_s)
                await asyncio.sleep(delay)
        finally:
            self._source = None
            if source is not None:  # cancelled while a source was up
                self._stop_now(source)


async def bind_with_retry(
    server: RobotServer,
    host: str,
    port: int,
    *,
    delay_s: float = 1.0,
    max_delay_s: float = 5.0,
) -> int:
    """Bind the server, retrying while the address is not available (Tailscale not up yet)."""
    while True:
        try:
            actual = await server.start(host, port)
        except OSError as error:
            log.warning("cannot bind %s:%s (%s); retrying in %.1f s", host, port, error, delay_s)
            await asyncio.sleep(delay_s)
            delay_s = min(delay_s * 2, max_delay_s)
            continue
        log.info("listening on %s:%s", host, actual)
        return actual


def _latest_stamp(source: Any) -> int | None:
    sample = source.latest
    return sample.t_ns if sample is not None else None


def build_devices(config: Config) -> tuple[SupervisedDevice, SupervisedDevice]:
    if config.simulate:

        def make_stm() -> Any:
            return SimulatedStm32()

        def make_lidar() -> Any:
            return SimulatedLidar()

    else:

        def make_stm() -> Any:
            return hardware.Stm32SerialSource(config.stm_port, baudrate=config.stm_baud)

        def make_lidar() -> Any:
            return hardware.N10PSerialSource(
                config.lidar_port,
                profile=hardware.N10P_PROTOCOL_PROFILE,
                baudrate=config.lidar_baud,
            )

    stm = SupervisedDevice("stm", make_stm, _latest_stamp, stale_s=2.0)
    lidar = SupervisedDevice("lidar", make_lidar, _latest_stamp, stale_s=3.0)
    return stm, lidar


async def run(config: Config) -> None:
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for signum in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(signum, stop.set)

    stm, lidar = build_devices(config)
    writer = CmdVelWriter(stm, motion_enabled=config.motion_enabled)
    server = RobotServer(
        token=config.link_token,
        writer=writer,
        stm=stm,
        devices=lambda: {"stm": stm.health(), "lidar": lidar.health()},
        lidar=lidar,
    )
    if not config.motion_enabled:
        log.warning("ROBOT_MOTION_ENABLED is false: only zero velocity will be written")
    if config.simulate:
        log.warning("ROBOT_SIMULATE is true: using simulated STM32 and LiDAR")

    writer.start()
    device_tasks = [asyncio.ensure_future(stm.run()), asyncio.ensure_future(lidar.run())]
    bind_task = asyncio.ensure_future(
        bind_with_retry(server, config.bind_host, config.bind_port)
    )
    try:
        await stop.wait()
    finally:
        log.info("shutting down")
        bind_task.cancel()
        await asyncio.gather(bind_task, return_exceptions=True)
        await server.close()  # each open connection clears the writer
        # The final zero goes out while the STM32 source is still running.
        if not await asyncio.to_thread(writer.stop):
            log.error("final zero velocity could not be written")
        for task in device_tasks:
            task.cancel()
        await asyncio.gather(*device_tasks, return_exceptions=True)  # stops the sources


def main() -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    try:
        config = load_config()
    except ConfigError as error:
        print(f"robot_agent: {error}", file=sys.stderr)
        return 2
    asyncio.run(run(config))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

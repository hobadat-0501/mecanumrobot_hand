"""Vision agent entry point: `python -m vision_agent`.

Skeleton (T19): runs the simulated pipeline (VISION_SIMULATE=true) or an idle one, sends
`vision_cmd` (always zero) to the robot agent at 20 Hz over PROTO-4 and serves PROTO-3.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
import socket
import sys
import time

from .config import Config, ConfigError, load_config
from .pipeline import Pipeline
from .server import VisionServer

log = logging.getLogger("vision_agent")
TICK_S = 0.05


class RobotLink:
    """PROTO-4 client: its own bound datagram socket so the robot can answer."""

    def __init__(self, robot_path: str, own_path: str) -> None:
        self._robot_path = robot_path
        self._own_path = own_path
        self._sock: socket.socket | None = None
        self.mode = False
        self.flag_stop = False
        self.status_ns: int | None = None
        self.seq = 0

    def open(self) -> bool:
        if not hasattr(socket, "AF_UNIX"):
            return False
        try:
            os.unlink(self._own_path)
        except OSError:
            pass
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        try:
            sock.bind(self._own_path)
        except OSError as exc:
            log.warning("cannot bind %s: %s", self._own_path, exc)
            sock.close()
            return False
        sock.setblocking(False)
        self._sock = sock
        return True

    def close(self) -> None:
        if self._sock is not None:
            self._sock.close()
            self._sock = None
            try:
                os.unlink(self._own_path)
            except OSError:
                pass

    def poll(self, now_ns: int) -> None:
        while self._sock is not None:
            try:
                data = self._sock.recv(2048)
            except (BlockingIOError, OSError):
                return
            try:
                msg = json.loads(data)
            except ValueError:
                continue
            if isinstance(msg, dict) and msg.get("t") == "robot_status":
                self.mode = bool(msg.get("mode"))
                self.flag_stop = bool(msg.get("flag_stop"))
                self.status_ns = now_ns

    def send_cmd(self, now_ns: int, state: str, user, cmd) -> None:
        if self._sock is None:
            return
        self.seq += 1
        payload = {
            "t": "vision_cmd", "seq": self.seq, "t_mono_ns": now_ns,
            "vx": cmd[0], "vy": cmd[1], "wz": cmd[2], "state": state, "user": user,
        }
        try:
            self._sock.sendto(json.dumps(payload, separators=(",", ":")).encode(), self._robot_path)
        except OSError:
            pass  # robot agent not up: it stays stopped by default


async def run(config: Config) -> None:
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for signum in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(signum, stop.set)
    pipeline = Pipeline(simulate=config.simulate)
    link = RobotLink(config.robot_socket, config.own_socket)
    if not link.open():
        log.warning("robot link unavailable: no status will arrive, the FSM stays in ESTOP/OFF")
    server = VisionServer(token=config.link_token, get_state=lambda: pipeline.vision_state(link.mode))
    await server.start(config.bind_host, config.bind_port)

    async def tick() -> None:
        seq, was_on = 0, False
        while True:
            now = time.monotonic_ns()
            link.poll(now)
            if link.mode != was_on:
                pipeline.mode_changed(link.mode, now)
                was_on = link.mode
            age = 99.0 if link.status_ns is None else (now - link.status_ns) / 1e9
            jpeg = pipeline.frame(now, status_age_s=age, flag_stop=link.flag_stop)
            seq += 1
            server.publish_frame(seq, now // 1_000_000, jpeg)
            link.send_cmd(now, pipeline.fsm.state, pipeline.fsm.user, pipeline.fsm.command())
            await asyncio.sleep(TICK_S)

    task = asyncio.ensure_future(tick())
    try:
        await stop.wait()
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        link.send_cmd(time.monotonic_ns(), "OFF", None, (0.0, 0.0, 0.0))
        await server.close()
        link.close()


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    try:
        config = load_config()
    except ConfigError as exc:
        log.error("%s", exc)
        return 2
    asyncio.run(run(config))
    return 0


if __name__ == "__main__":
    sys.exit(main())

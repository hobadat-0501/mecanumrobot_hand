"""Local link to the vision agent (PROTO-4): a unix datagram socket on the Jetson.

Up (vision -> robot): {"t":"vision_cmd","seq","t_mono_ns","vx","vy","wz","state","user"} at 20 Hz,
velocities in STM32 wire units. Down (robot -> vision): {"t":"robot_status",...} at 20 Hz, sent to
the address of the last datagram received, so the vision agent must bind its own socket path.
Datagrams are small JSON texts; anything malformed is dropped and counted.
"""
from __future__ import annotations

import asyncio
import json
import logging
import math
import os
import socket
from collections.abc import Callable
from typing import Any

log = logging.getLogger("robot_agent.local_link")

MAX_DATAGRAM_BYTES = 1024
STATUS_PERIOD_S = 0.05
_CMD_KEYS = frozenset(("t", "seq", "t_mono_ns", "vx", "vy", "wz", "state", "user"))


def _number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _integer(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def parse_vision_cmd(data: Any) -> tuple[int, int, float, float, float, str] | None:
    """Return (seq, t_mono_ns, vx, vy, wz, state) for a well-formed vision_cmd, else None."""
    if not isinstance(data, dict) or set(data) != _CMD_KEYS or data["t"] != "vision_cmd":
        return None
    if not (_integer(data["seq"]) and _integer(data["t_mono_ns"])):
        return None
    if not all(_number(data[k]) for k in ("vx", "vy", "wz")):
        return None
    if not all(math.isfinite(data[k]) for k in ("vx", "vy", "wz")):
        return None
    if not isinstance(data["state"], str) or not isinstance(data["user"], (str, int, type(None))):
        return None
    return (
        data["seq"],
        data["t_mono_ns"],
        float(data["vx"]),
        float(data["vy"]),
        float(data["wz"]),
        data["state"],
    )


class _Protocol(asyncio.DatagramProtocol):
    def __init__(self, link: "VisionLink") -> None:
        self._link = link

    def connection_made(self, transport: Any) -> None:
        self._link._transport = transport

    def datagram_received(self, data: bytes, addr: Any) -> None:
        self._link.on_datagram(data, addr)


class VisionLink:
    def __init__(self, arbiter: Any, stm: Any, path: str) -> None:
        self._arbiter = arbiter
        self._stm = stm
        self._path = path
        self._transport: Any = None
        self._peer: Any = None
        self._sock: socket.socket | None = None
        self.dropped = 0

    def on_datagram(self, data: bytes, addr: Any) -> None:
        if addr:
            self._peer = addr
        command = None
        if len(data) <= MAX_DATAGRAM_BYTES:
            try:
                command = parse_vision_cmd(json.loads(data.decode("utf-8")))
            except (ValueError, RecursionError):
                command = None
        if command is None:
            self.dropped += 1
            return
        self._arbiter.submit_vision(*command)

    async def start(self) -> None:
        if not hasattr(socket, "AF_UNIX"):
            raise OSError("unix datagram sockets are not available on this platform")
        directory = os.path.dirname(self._path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        try:
            os.unlink(self._path)  # stale socket from a previous run
        except FileNotFoundError:
            pass
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        sock.bind(self._path)
        os.chmod(self._path, 0o660)
        sock.setblocking(False)
        self._sock = sock
        loop = asyncio.get_running_loop()
        await loop.create_datagram_endpoint(lambda: _Protocol(self), sock=sock)

    def stop(self) -> None:
        if self._transport is not None:
            self._transport.close()
            self._transport = None
        try:
            os.unlink(self._path)
        except OSError:
            pass

    def send_status(self) -> bool:
        if self._transport is None or not self._peer:
            return False
        payload = self._arbiter.robot_status(self._stm.latest)
        try:
            self._transport.sendto(json.dumps(payload, separators=(",", ":")).encode(), self._peer)
        except OSError:
            return False  # vision agent gone or its buffer full: never block, never queue
        return True

    async def run_status(self, period_s: float = STATUS_PERIOD_S) -> None:
        while True:
            try:
                self.send_status()
            except Exception:
                log.exception("robot_status failed")
            await asyncio.sleep(period_s)


async def arbiter_loop(arbiter: Any, period_s: float = 0.05, on_error: Callable[[], None] | None = None) -> None:
    """Drive CmdArbiter.step() at 20 Hz; an exception in one round must not end the loop."""
    while True:
        try:
            arbiter.step()
        except Exception:
            log.exception("arbiter step failed")
            if on_error is not None:
                on_error()
        await asyncio.sleep(period_s)

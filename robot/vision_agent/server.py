"""PROTO-3 server: app server <-> vision agent on ws://<tailscale-ip>:8766/ws.

Up: `vision_state` JSON at <= 10 Hz and binary JPEG frames (type u8 = 3, ver u8, seq u32,
t_mono_ms u64 + JPEG), only the newest frame is kept per client. Down: staff/enroll commands are
accepted here as JSON objects and passed to `on_command` (their handling arrives in T22).
No message carries a velocity.
"""
from __future__ import annotations

import asyncio
import hmac
import json
import logging
import struct
from collections.abc import Callable
from http import HTTPStatus
from typing import Any
from urllib.parse import urlsplit

from websockets.asyncio.server import serve

log = logging.getLogger("vision_agent.server")

WS_PATH = "/ws"
FRAME_TYPE = 3
FRAME_VER = 1
MAX_MESSAGE_BYTES = 64 * 1024
STATE_PERIOD_S = 0.1
COMMANDS = frozenset(
    (
        "staff_list", "staff_create", "staff_update", "staff_delete",
        "enroll_start", "enroll_capture", "enroll_commit", "enroll_cancel", "faces_clear",
    )
)


def encode_frame(seq: int, t_mono_ms: int, jpeg: bytes) -> bytes:
    return struct.pack("<BBIQ", FRAME_TYPE, FRAME_VER, seq & 0xFFFFFFFF, max(0, t_mono_ms)) + jpeg


class VisionServer:
    def __init__(
        self,
        *,
        token: str,
        get_state: Callable[[], dict[str, Any]],
        on_command: Callable[[dict[str, Any]], dict[str, Any] | None] | None = None,
    ) -> None:
        if not token:
            raise ValueError("link token must not be empty")
        self._expected = f"Bearer {token}".encode()
        self._get_state = get_state
        self._on_command = on_command
        self._server: Any = None
        self._clients: set[Any] = set()
        self._frame: tuple[int, int, bytes] | None = None  # newest only
        self._frame_event = asyncio.Event()

    def publish_frame(self, seq: int, t_mono_ms: int, jpeg: bytes) -> None:
        self._frame = (seq, t_mono_ms, jpeg)
        self._frame_event.set()

    async def start(self, host: str, port: int) -> int:
        self._server = await serve(
            self._handler, host, port,
            process_request=self._process_request,
            max_size=MAX_MESSAGE_BYTES, compression=None, ping_interval=2, ping_timeout=2,
        )
        return int(self._server.sockets[0].getsockname()[1])

    async def close(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

    def _process_request(self, connection: Any, request: Any) -> Any:
        if urlsplit(request.path).path != WS_PATH:
            return connection.respond(HTTPStatus.NOT_FOUND, "not found\n")
        values = request.headers.get_all("Authorization")
        try:
            ok = len(values) == 1 and hmac.compare_digest(values[0].encode(), self._expected)
        except UnicodeEncodeError:
            ok = False
        if not ok:
            return connection.respond(HTTPStatus.UNAUTHORIZED, "unauthorized\n")
        return None

    async def _handler(self, ws: Any) -> None:
        self._clients.add(ws)
        senders = [asyncio.ensure_future(self._send_state(ws)), asyncio.ensure_future(self._send_frames(ws))]
        try:
            async for message in ws:
                await self._on_message(ws, message)
        except Exception:
            log.debug("vision client dropped", exc_info=True)
        finally:
            self._clients.discard(ws)
            for task in senders:
                task.cancel()
            await asyncio.gather(*senders, return_exceptions=True)

    async def _on_message(self, ws: Any, message: Any) -> None:
        if not isinstance(message, str):
            return
        try:
            data = json.loads(message)
        except (ValueError, RecursionError):
            return
        if not isinstance(data, dict) or data.get("t") not in COMMANDS:
            return  # unknown or velocity-like messages are ignored, never forwarded
        result = self._on_command(data) if self._on_command is not None else None
        reply = {"t": "result", "of": data["t"], "ok": result is not None, **(result or {})}
        await ws.send(json.dumps(reply, separators=(",", ":")))

    async def _send_state(self, ws: Any) -> None:
        while True:
            await ws.send(json.dumps(self._get_state(), separators=(",", ":")))
            await asyncio.sleep(STATE_PERIOD_S)

    async def _send_frames(self, ws: Any) -> None:
        last = -1
        while True:
            await self._frame_event.wait()
            self._frame_event.clear()
            frame = self._frame
            if frame is None or frame[0] == last:
                continue
            last = frame[0]
            await ws.send(encode_frame(*frame))

"""WebSocket client from the app server to the vision agent (PROTO-3).

Receives `vision_state` JSON, `result` replies and binary JPEG frames (type 3). Sends only the
staff/enroll management commands; nothing sent or received here carries a velocity. Reconnects
forever with back-off. Frames are latest-only.
"""

from __future__ import annotations

import asyncio
import json
import logging
import struct
from typing import Any, Callable, Dict, Optional

from websockets.asyncio.client import connect

log = logging.getLogger("app_server.vision_link")

MAX_MESSAGE_BYTES = 1 << 20
FRAME_TYPE = 3
FRAME_HEADER = 14
COMMANDS = frozenset(
    (
        "staff_list", "staff_create", "staff_update", "staff_delete",
        "enroll_start", "enroll_capture", "enroll_commit", "enroll_cancel", "faces_clear",
    )
)


class VisionLink:
    def __init__(
        self,
        url: str,
        token: str,
        *,
        on_state: Callable[[Dict[str, Any]], None],
        on_result: Optional[Callable[[Dict[str, Any]], None]] = None,
        on_disconnect: Optional[Callable[[], None]] = None,
        backoff_initial_s: float = 0.5,
        backoff_max_s: float = 3.0,
    ) -> None:
        self._url = url
        self._headers = {"Authorization": "Bearer " + token}
        self._on_state = on_state
        self._on_result = on_result
        self._on_disconnect = on_disconnect
        self._backoff_initial_s = backoff_initial_s
        self._backoff_max_s = backoff_max_s
        self._ws: Any = None
        self._connected = False
        self.frame: Optional[bytes] = None  # newest JPEG
        self.frame_seq = 0

    @property
    def connected(self) -> bool:
        return self._connected

    async def send_command(self, data: Dict[str, Any]) -> bool:
        """Forward one management command. Unknown types and a down link are refused."""
        if not self._connected or data.get("t") not in COMMANDS:
            return False
        try:
            await self._ws.send(json.dumps(data, separators=(",", ":")))
        except Exception:
            return False
        return True

    async def run(self) -> None:
        delay = self._backoff_initial_s
        while True:
            try:
                async with connect(
                    self._url,
                    additional_headers=self._headers,
                    compression=None,
                    max_size=MAX_MESSAGE_BYTES,
                    ping_interval=2.0,
                    ping_timeout=2.0,
                    open_timeout=3.0,
                ) as ws:
                    delay = self._backoff_initial_s
                    self._ws, self._connected = ws, True
                    try:
                        await self._receive(ws)
                    finally:
                        self._ws, self._connected, self.frame = None, False, None
                        if self._on_disconnect is not None:
                            self._on_disconnect()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                log.info("vision link: %s: %s", type(exc).__name__, exc)
            await asyncio.sleep(delay)
            delay = min(delay * 2, self._backoff_max_s)

    async def _receive(self, ws: Any) -> None:
        async for message in ws:
            if not isinstance(message, str):
                if len(message) > FRAME_HEADER and message[0] == FRAME_TYPE:
                    self.frame = bytes(message[FRAME_HEADER:])
                    self.frame_seq = struct.unpack_from("<I", message, 2)[0]
                continue
            try:
                data = json.loads(message)
            except (ValueError, RecursionError):
                continue
            if not isinstance(data, dict):
                continue
            try:
                if data.get("t") == "vision_state":
                    self._on_state(data)
                elif data.get("t") == "result" and self._on_result is not None:
                    self._on_result(data)
            except Exception:
                log.exception("vision handler failed")

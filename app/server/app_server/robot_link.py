"""WebSocket client from the app server down to the robot (PROTO-2).

Connects to ROBOT_WS_URL with `Authorization: Bearer <token>` and reconnects forever with
back-off. The only thing sent down is `cmd_vel` with exactly the keys t, seq, vx, vy, wz in
wire units. Outbound commands are latest-only: one slot, newer replaces older, so no backlog
can build up (NFR-03). A command is never stored while the link is down or carried across a
reconnect (SAF-03). Incoming `state` messages are handed to `on_state`; binary frames are
forwarded to `on_scan` unchanged after a size/type check (PROTO-2).
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, Callable, Dict, Optional

from websockets.asyncio.client import connect

log = logging.getLogger("app_server.robot_link")

MAX_MESSAGE_BYTES = 1 << 20
# Scan frame layout (PROTO-2), see robot_agent.server: u8 type, u8 ver, u32 seq, u64 t_mono_ms,
# then 360 x u16. The frame is relayed byte for byte; only type and size are checked here.
SCAN_FRAME_TYPE = 2
SCAN_FRAME_SIZE = 14 + 2 * 360


class RobotLink:
    def __init__(
        self,
        url: str,
        token: str,
        *,
        on_state: Callable[[Dict[str, Any]], None],
        on_scan: Optional[Callable[[bytes], None]] = None,
        on_connect: Optional[Callable[[], None]] = None,
        on_disconnect: Optional[Callable[[], None]] = None,
        backoff_initial_s: float = 0.2,
        backoff_max_s: float = 2.0,
        ping_interval_s: float = 2.0,
        ping_timeout_s: float = 2.0,
        open_timeout_s: float = 3.0,
        rtt_interval_s: float = 1.0,
    ) -> None:
        self._url = url
        self._headers = {"Authorization": "Bearer " + token}
        self._on_state = on_state
        self._on_scan = on_scan
        self._on_connect = on_connect
        self._on_disconnect = on_disconnect
        self._backoff_initial_s = backoff_initial_s
        self._backoff_max_s = backoff_max_s
        self._ping_interval_s = ping_interval_s
        self._ping_timeout_s = ping_timeout_s
        self._open_timeout_s = open_timeout_s
        self._connected = False
        self._ws: Any = None
        self._pending: Optional[str] = None
        self._wake = asyncio.Event()
        self._last_seq = 0
        self._rtt_s: Optional[float] = None
        self._rtt_interval_s = rtt_interval_s

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def latency_s(self) -> Optional[float]:
        """Round-trip time of the last measured ping, or None when unknown."""
        return self._rtt_s if self._ws is not None else None

    def send_cmd_vel(self, seq: int, vx: float, vy: float, wz: float) -> bool:
        """Queue the newest cmd_vel (wire units), replacing any unsent one.

        Returns False and drops the command when the link is down.
        """
        if not self._connected:
            return False
        self._last_seq = seq
        self._pending = json.dumps(
            {"t": "cmd_vel", "seq": seq, "vx": vx, "vy": vy, "wz": wz},
            separators=(",", ":"),
        )
        self._wake.set()
        return True

    def send_zero(self) -> bool:
        """Queue a zero cmd_vel that replaces any unsent command."""
        return self.send_cmd_vel(self._last_seq, 0.0, 0.0, 0.0)

    def _notify(self, callback: Optional[Callable[[], None]]) -> None:
        if callback is None:
            return
        try:
            callback()
        except Exception:
            log.exception("robot link callback failed")

    async def run(self) -> None:
        """Connect, serve until the link drops, back off, repeat. Cancel to stop."""
        delay = self._backoff_initial_s
        while True:
            try:
                async with connect(
                    self._url,
                    additional_headers=self._headers,
                    compression=None,
                    max_size=MAX_MESSAGE_BYTES,
                    ping_interval=self._ping_interval_s,
                    ping_timeout=self._ping_timeout_s,
                    open_timeout=self._open_timeout_s,
                ) as ws:
                    delay = self._backoff_initial_s
                    await self._session(ws)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                log.info("robot link: %s: %s", type(exc).__name__, exc)
            await asyncio.sleep(delay)
            delay = min(delay * 2, self._backoff_max_s)

    async def _session(self, ws: Any) -> None:
        self._ws = ws
        self._pending = None
        self._wake.clear()
        self._connected = True
        self._rtt_s = None
        sender = asyncio.ensure_future(self._send_loop(ws))
        receiver = asyncio.ensure_future(self._receive_loop(ws))
        pinger = asyncio.ensure_future(self._rtt_loop(ws))
        try:
            self._notify(self._on_connect)
            await asyncio.wait({sender, receiver}, return_when=asyncio.FIRST_COMPLETED)
        finally:
            self._connected = False
            self._ws = None
            self._rtt_s = None
            pinger.cancel()
            self._pending = None
            self._notify(self._on_disconnect)
            sender.cancel()
            receiver.cancel()
            await asyncio.gather(sender, receiver, pinger, return_exceptions=True)

    async def _rtt_loop(self, ws: Any) -> None:
        """Measure the round trip with an explicit ping (the keepalive value is unreliable)."""
        while True:
            try:
                started = time.monotonic()
                pong = await ws.ping()
                await asyncio.wait_for(pong, timeout=self._ping_timeout_s)
                self._rtt_s = time.monotonic() - started
            except asyncio.CancelledError:
                raise
            except Exception:
                self._rtt_s = None
            await asyncio.sleep(self._rtt_interval_s)

    async def _send_loop(self, ws: Any) -> None:
        while True:
            await self._wake.wait()
            self._wake.clear()
            text, self._pending = self._pending, None
            if text is not None:
                await ws.send(text)

    async def _receive_loop(self, ws: Any) -> None:
        async for message in ws:
            if not isinstance(message, str):
                if (
                    self._on_scan is not None
                    and len(message) == SCAN_FRAME_SIZE
                    and message[0] == SCAN_FRAME_TYPE
                ):
                    try:
                        self._on_scan(bytes(message))
                    except Exception:
                        log.exception("robot scan handler failed")
                continue
            try:
                data = json.loads(message)
            except (ValueError, RecursionError):
                continue
            if isinstance(data, dict) and data.get("t") == "state":
                try:
                    self._on_state(data)
                except Exception:
                    log.exception("robot state handler failed")

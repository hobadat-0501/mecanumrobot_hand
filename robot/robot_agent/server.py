"""Robot WebSocket server (PROTO-2): ws://<ROBOT_BIND_HOST>:<ROBOT_BIND_PORT>/ws.

Down: only {"t":"cmd_vel","seq","vx","vy","wz"} (wire units) reaches the writer (FR-03).
Up: JSON "state" at most 50 Hz. Binary "scan" frames are added in T13 (see _send_extras).
The robot knows nothing about the app-side scale factor.
"""
from __future__ import annotations

import asyncio
import hmac
import json
import time
from collections.abc import Callable
from http import HTTPStatus
from typing import Any
from urllib.parse import urlsplit

from websockets.asyncio.server import serve
from websockets.exceptions import ConnectionClosed

WS_PATH = "/ws"
MAX_STATE_HZ = 50.0
MAX_MESSAGE_BYTES = 1024
CLOSE_REPLACED = 4000
_CMD_KEYS = frozenset(("t", "seq", "vx", "vy", "wz"))


def _number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def parse_cmd_vel(data: Any) -> tuple[int, float, float, float] | None:
    """Return (seq, vx, vy, wz) for a well-formed cmd_vel message, else None."""
    if not isinstance(data, dict) or set(data) != _CMD_KEYS or data["t"] != "cmd_vel":
        return None
    seq = data["seq"]
    if isinstance(seq, bool) or not isinstance(seq, int):
        return None
    if not (_number(data["vx"]) and _number(data["vy"]) and _number(data["wz"])):
        return None
    return seq, data["vx"], data["vy"], data["wz"]


class RobotServer:
    def __init__(
        self,
        *,
        token: str,
        writer: Any,
        stm: Any,
        devices: Callable[[], dict[str, dict[str, Any]]],
        state_hz: float = MAX_STATE_HZ,
    ) -> None:
        """writer: CmdVelWriter. stm: object with latest/latest_aux (may return None).
        devices: returns {"stm": {...}, "lidar": {...}} health dicts from the supervisors."""
        if not token:
            raise ValueError("link token must not be empty")
        if not 0.0 < state_hz <= MAX_STATE_HZ:
            raise ValueError(f"state_hz must be in (0, {MAX_STATE_HZ}]")
        self._expected = ("Bearer " + token).encode("utf-8")
        self.writer = writer
        self._stm = stm
        self._devices = devices
        self._period_s = 1.0 / state_hz
        self._server: Any = None
        self._current: Any = None
        self._closers: set[asyncio.Future] = set()
        self._last_cmd_seq: int | None = None
        self.ignored = 0  # messages dropped without reaching the writer

    # ---- lifecycle ----

    async def start(self, host: str, port: int) -> int:
        """Bind and serve. Raises OSError if the address is not available. Returns the port."""
        self._server = await serve(
            self._handler,
            host,
            port,
            process_request=self._process_request,
            max_size=MAX_MESSAGE_BYTES,
            compression=None,
            ping_interval=2,
            ping_timeout=2,
        )
        return int(self._server.sockets[0].getsockname()[1])

    async def close(self) -> None:
        if self._server is not None:
            self._server.close()  # closes live connections; each handler then clears the writer
            await self._server.wait_closed()
            self._server = None

    # ---- handshake ----

    def _authorized(self, header: str | None) -> bool:
        return hmac.compare_digest((header or "").encode("utf-8"), self._expected)

    def _process_request(self, connection: Any, request: Any) -> Any:
        if urlsplit(request.path).path != WS_PATH:
            return connection.respond(HTTPStatus.NOT_FOUND, "not found\n")
        if not self._authorized(request.headers.get("Authorization")):
            return connection.respond(HTTPStatus.UNAUTHORIZED, "unauthorized\n")
        return None

    # ---- one connection ----

    def _claim(self, conn: Any) -> None:
        """The newest valid connection replaces the old one (SAF-07)."""
        old, self._current = self._current, conn
        self._last_cmd_seq = None
        if old is not None:
            self.writer.clear()  # SAF-03c: the replaced link's command must not survive
            closer = asyncio.ensure_future(old.close(CLOSE_REPLACED, "replaced"))
            self._closers.add(closer)
            closer.add_done_callback(self._closers.discard)

    def _release(self, conn: Any) -> None:
        if self._current is conn:
            self._current = None
            self._last_cmd_seq = None
            self.writer.clear()  # SAF-03c: link lost -> writer returns to zero

    async def _handler(self, conn: Any) -> None:
        self._claim(conn)
        sender = asyncio.ensure_future(self._send_states(conn))
        try:
            async for message in conn:
                if self._current is not conn:
                    break
                self._on_message(message)
        except ConnectionClosed:
            pass
        finally:
            self._release(conn)
            sender.cancel()
            await asyncio.gather(sender, return_exceptions=True)

    def _on_message(self, message: str | bytes) -> None:
        command = None
        if isinstance(message, str):
            try:
                command = parse_cmd_vel(json.loads(message))
            except (ValueError, RecursionError):
                command = None
        if command is None:  # binary frame, bad JSON, or anything but a valid cmd_vel
            self.ignored += 1
            return
        seq, vx, vy, wz = command
        if self.writer.set_cmd_vel(vx, vy, wz):
            self._last_cmd_seq = seq

    # ---- state out ----

    def build_state(self) -> dict[str, Any]:
        sample = self._stm.latest
        aux = self._stm.latest_aux
        devices = self._devices()
        health = self.writer.health()
        state: dict[str, Any] = {
            "t": "state",
            "t_mono_ns": sample.t_ns if sample is not None else time.monotonic_ns(),
            "last_cmd_seq": self._last_cmd_seq,
            "vel": None,
            "imu": None,
            "voltage": None,
            "flag_stop": None,
            "charge": None,
            "health": {
                "stm": devices["stm"],
                "lidar": devices["lidar"],
                "writer": {
                    "running": health.running,
                    "healthy": health.healthy,
                    "error_count": health.error_count,
                    "last_error": health.last_error,
                    "rejected_count": health.rejected_count,
                },
            },
        }
        if sample is not None:
            state["vel"] = {"vx": sample.vx_mps, "vy": sample.vy_mps, "wz": sample.wz_radps}
            state["imu"] = {
                "ax": sample.accel_x_mps2,
                "ay": sample.accel_y_mps2,
                "az": sample.accel_z_mps2,
                "gx": sample.gyro_x_radps,
                "gy": sample.gyro_y_radps,
                "gz": sample.gyro_z_radps,
            }
            state["voltage"] = sample.voltage_v
            state["flag_stop"] = sample.flag_stop
        if aux is not None:
            state["charge"] = {
                "current_a": aux.charging_current_a,
                "red": aux.red,
                "charging": aux.charging,
                "set_state": aux.charge_set_state,
            }
        return state

    async def _send_states(self, conn: Any) -> None:
        # One send at a time: a slow peer only ever receives the newest state, because the next
        # state is built after the previous send finished. No queue, no backlog (NFR-03).
        loop = asyncio.get_running_loop()
        due = loop.time()
        try:
            while self._current is conn:
                await conn.send(json.dumps(self.build_state(), separators=(",", ":")))
                await self._send_extras(conn)
                due += self._period_s
                now = loop.time()
                if due < now:
                    due = now  # fell behind: skip ahead, never burst above the rate limit
                await asyncio.sleep(due - now)
        except ConnectionClosed:
            return

    async def _send_extras(self, conn: Any) -> None:
        """T13 adds binary `scan` frames here (PROTO-2). Intentionally empty in T04."""

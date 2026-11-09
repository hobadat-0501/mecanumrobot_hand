"""Robot WebSocket server (PROTO-2): ws://<ROBOT_BIND_HOST>:<ROBOT_BIND_PORT>/ws.

Down: only {"t":"cmd_vel","seq","vx","vy","wz"} (wire units) reaches the writer (FR-03).
Up: JSON "state" at most 50 Hz, and binary "scan" frames at most 10 Hz (see build_scan_frame).
The robot knows nothing about the app-side scale factor.
"""
from __future__ import annotations

import asyncio
import hmac
import json
import math
import struct
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

# Binary scan frame (PROTO-2), little-endian, defined only here (the client mirrors it in
# protocol.ts): header `type u8, ver u8, seq u32, t_mono_ms u64` (14 bytes), then SCAN_BINS x u16
# range in millimetres, 0 = no point. Bin i covers angle i degrees (bin 0 at angle 0, increasing
# counter-clockwise, as delivered by the LiDAR source); a point goes to round(degrees) mod 360 and
# the nearest point of a bin wins. `seq` counts the scan frames sent on one connection.
SCAN_FRAME_TYPE = 2  # 1 is unused; the JSON "state" is a text frame and has no binary type
SCAN_FRAME_VER = 1
SCAN_BINS = 360
SCAN_HEADER = struct.Struct("<BBIQ")
SCAN_FRAME_SIZE = SCAN_HEADER.size + 2 * SCAN_BINS
MAX_SCAN_HZ = 10.0
_SCAN_MIN_INTERVAL_S = 0.95 / MAX_SCAN_HZ  # slack so a 10 Hz source is not aliased down
_U16_MAX = 0xFFFF


def build_scan_frame(scan: Any, seq: int) -> bytes:
    """Encode a LidarScan as a PROTO-2 scan frame. Non-finite or non-positive ranges are skipped."""
    ranges = [0] * SCAN_BINS
    for point in scan.points:
        angle, distance = point.angle_rad, point.range_m
        if not (math.isfinite(angle) and math.isfinite(distance)) or distance <= 0.0:
            continue
        mm = min(max(1, round(distance * 1000.0)), _U16_MAX)
        index = round(math.degrees(angle)) % SCAN_BINS
        if ranges[index] == 0 or mm < ranges[index]:
            ranges[index] = mm
    header = SCAN_HEADER.pack(
        SCAN_FRAME_TYPE, SCAN_FRAME_VER, seq & 0xFFFFFFFF, max(0, scan.t_ns // 1_000_000)
    )
    return header + struct.pack(f"<{SCAN_BINS}H", *ranges)


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
        lidar: Any = None,
    ) -> None:
        """writer: CmdVelWriter. stm: object with latest/latest_aux (may return None).
        devices: returns {"stm": {...}, "lidar": {...}} health dicts from the supervisors.
        lidar: optional object whose `latest` is a LidarScan or None; enables scan frames."""
        if not token:
            raise ValueError("link token must not be empty")
        if not 0.0 < state_hz <= MAX_STATE_HZ:
            raise ValueError(f"state_hz must be in (0, {MAX_STATE_HZ}]")
        self._expected = ("Bearer " + token).encode("utf-8")
        self.writer = writer
        self._stm = stm
        self._devices = devices
        self._lidar = lidar
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
        scan_progress = _ScanProgress()
        try:
            while self._current is conn:
                await conn.send(json.dumps(self.build_state(), separators=(",", ":")))
                await self._send_extras(conn, scan_progress)
                due += self._period_s
                now = loop.time()
                if due < now:
                    due = now  # fell behind: skip ahead, never burst above the rate limit
                await asyncio.sleep(due - now)
        except ConnectionClosed:
            return

    async def _send_extras(self, conn: Any, progress: "_ScanProgress") -> None:
        """Send the newest LiDAR scan as a binary frame: only if it is new and at most 10 Hz.

        Awaited inline like the state send, so a slow peer only ever gets the newest scan."""
        scan = self._lidar.latest if self._lidar is not None else None
        if scan is None or scan.t_ns == progress.last_t_ns:
            return
        now = time.monotonic()
        if now - progress.last_sent_s < _SCAN_MIN_INTERVAL_S:
            return
        progress.last_t_ns = scan.t_ns
        progress.last_sent_s = now
        progress.seq += 1
        await conn.send(build_scan_frame(scan, progress.seq))


class _ScanProgress:
    """Per-connection scan bookkeeping."""

    def __init__(self) -> None:
        self.seq = 0
        self.last_t_ns: int | None = None
        self.last_sent_s = -math.inf

"""App server: FastAPI app with the operator WebSocket (PROTO-1) and a health endpoint.

Wires ControlSession (arm, driving rights, unit conversion), RobotLink (WS client down to the
robot) and Telemetry (scaling, odometry, state). State goes to each web client at most
STATE_HZ times per second through a latest-only per-client mailbox, so a slow client only
ever lags itself (NFR-03). The newest LiDAR scan frame from the robot is relayed unchanged as a
binary frame, at most SCAN_HZ times per second, through a second latest-only slot per client. Run with `python -m app_server.main`.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import Any, Callable, Dict, Mapping, Optional

import uvicorn
from fastapi import FastAPI, WebSocket

from .config import Settings, load_settings
from .control import ControlSession
from .robot_link import RobotLink
from .telemetry import Telemetry

log = logging.getLogger("app_server")

STATE_HZ = 20.0
SCAN_HZ = 10.0
SCAN_TICK_S = 0.02
WATCHDOG_TICK_S = 0.05
MAX_MESSAGE_CHARS = 4096
WS_MAX_SIZE_BYTES = 65536


class Client:
    """One connected web client with a latest-only outbox and its own sender task."""

    def __init__(self, client_id: str, ws: Any) -> None:
        self.client_id = client_id
        self._ws = ws
        self._latest: Optional[str] = None
        self._latest_scan: Optional[bytes] = None
        self._event = asyncio.Event()
        self._task = asyncio.ensure_future(self._run())

    def offer(self, text: str) -> None:
        """Replace the unsent state with `text`. Never blocks."""
        self._latest = text
        self._event.set()

    def offer_scan(self, frame: bytes) -> None:
        """Replace the unsent scan frame with `frame`. Never blocks."""
        self._latest_scan = frame
        self._event.set()

    def close(self) -> None:
        self._task.cancel()

    async def _run(self) -> None:
        try:
            while True:
                await self._event.wait()
                self._event.clear()
                text, self._latest = self._latest, None
                frame, self._latest_scan = self._latest_scan, None
                if text is not None:
                    await self._ws.send_text(text)
                if frame is not None:
                    await self._ws.send_bytes(frame)
        except asyncio.CancelledError:
            raise
        except Exception:
            return  # the peer is gone; the receive loop ends the connection


class Hub:
    """The set of web clients; publishing never waits for any of them."""

    def __init__(self) -> None:
        self._clients: Dict[str, Client] = {}

    def __len__(self) -> int:
        return len(self._clients)

    def add(self, client_id: str, ws: Any) -> Client:
        client = Client(client_id, ws)
        self._clients[client_id] = client
        return client

    def remove(self, client_id: str) -> None:
        client = self._clients.pop(client_id, None)
        if client is not None:
            client.close()

    def publish_scan(self, frame: bytes) -> None:
        for client in list(self._clients.values()):
            client.offer_scan(frame)

    def publish(self, state: Dict[str, Any], role_of: Callable[[str], Optional[str]]) -> None:
        """Offer `state` to every client, adding that client's own role under `session`."""
        for client in list(self._clients.values()):
            payload = dict(state)
            payload["session"] = dict(state["session"], role=role_of(client.client_id))
            client.offer(json.dumps(payload, separators=(",", ":")))


def create_app(
    settings: Settings,
    *,
    clock: Callable[[], float] = time.monotonic,
    state_hz: float = STATE_HZ,
    scan_hz: float = SCAN_HZ,
    watchdog_tick_s: float = WATCHDOG_TICK_S,
    backoff_initial_s: float = 0.2,
    backoff_max_s: float = 2.0,
) -> FastAPI:
    session = ControlSession(settings.operator_token, settings.allowed_origins, clock, settings.speed_scale)
    telemetry = Telemetry(settings.speed_scale)
    hub = Hub()
    latest_scan: Dict[str, Any] = {"frame": None, "sent": None}

    def on_scan(frame: bytes) -> None:
        latest_scan["frame"] = frame  # latest only: an unforwarded older scan is replaced

    def on_link_up() -> None:
        link.send_zero()  # a fresh link always starts at zero, whatever happened before

    def on_link_down() -> None:
        telemetry.clear_robot()
        latest_scan["frame"] = latest_scan["sent"] = None
        if session.armed and session.driver is not None:
            session.arm(session.driver, False)  # SAF-03: stay disarmed until re-armed

    link = RobotLink(
        settings.robot_ws_url,
        settings.robot_link_token,
        on_state=telemetry.on_robot_state,
        on_scan=on_scan,
        on_connect=on_link_up,
        on_disconnect=on_link_down,
        backoff_initial_s=backoff_initial_s,
        backoff_max_s=backoff_max_s,
    )

    def build_state() -> Dict[str, Any]:
        return telemetry.build_state(session.snapshot(), link.connected, link.latency_s)

    async def broadcast_loop() -> None:
        loop = asyncio.get_running_loop()
        period = 1.0 / state_hz
        due = loop.time()
        while True:
            try:
                hub.publish(build_state(), session.role)
            except Exception:
                log.exception("broadcast iteration failed")  # one bad iteration must not end the loop
            due += period
            now = loop.time()
            if due < now:
                due = now  # fell behind: skip ahead, never burst above the rate limit
            await asyncio.sleep(due - now)

    async def scan_loop() -> None:
        # Forward the newest unsent scan, at most scan_hz times per second.
        last = -1e9
        while True:
            frame = latest_scan["frame"]
            now = time.monotonic()
            if frame is not None and frame is not latest_scan["sent"] and now - last >= 1.0 / scan_hz:
                latest_scan["sent"] = frame
                last = now
                hub.publish_scan(frame)
            await asyncio.sleep(SCAN_TICK_S)

    async def watchdog_loop() -> None:
        while True:
            try:
                if session.watchdog_tripped():
                    link.send_zero()
            except Exception:
                log.exception("watchdog iteration failed")  # keep watching, SAF-03
            await asyncio.sleep(watchdog_tick_s)

    def handle_text(client_id: str, text: str) -> None:
        if len(text) > MAX_MESSAGE_CHARS:
            return
        try:
            msg = json.loads(text)
        except (ValueError, RecursionError):
            return
        if not isinstance(msg, dict):
            return
        kind = msg.get("t", msg.get("type"))
        if kind == "hello":
            session.hello(client_id, msg.get("token"))
        elif kind == "cmd_vel":
            try:
                wire = session.handle_cmd_vel(client_id, msg)
            except ValueError:
                return  # drop only this message
            if wire is not None:
                link.send_cmd_vel(wire["seq"], wire["vx"], wire["vy"], wire["wz"])
        elif kind == "arm":
            on = msg.get("on")
            if on is True and not link.connected:
                return  # no arming without a robot link
            if session.arm(client_id, on) and on is False:
                link.send_zero()
        elif kind == "odom_reset":
            if session.role(client_id) == "driver":
                telemetry.reset_odometry()

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        tasks = [
            asyncio.ensure_future(link.run()),
            asyncio.ensure_future(broadcast_loop()),
            asyncio.ensure_future(scan_loop()),
            asyncio.ensure_future(watchdog_loop()),
        ]
        try:
            yield
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.runtime = SimpleNamespace(session=session, link=link, telemetry=telemetry, hub=hub)

    @app.get("/health")
    async def health() -> Dict[str, Any]:
        return {"ok": True, "robot_link": link.connected, "clients": len(hub)}

    @app.websocket("/ws/operator")
    async def operator(ws: WebSocket) -> None:
        client_id = uuid.uuid4().hex
        if not session.connect(client_id, ws.headers.get("origin")):
            await ws.close(code=1008)  # refused before accept
            return
        try:
            await ws.accept()
            hub.add(client_id, ws)
            while True:
                message = await ws.receive()
                if message["type"] == "websocket.disconnect":
                    break
                text = message.get("text")
                if text is not None:
                    handle_text(client_id, text)
        finally:
            hub.remove(client_id)
            if session.disconnect(client_id):
                link.send_zero()

    return app


def main(env: Optional[Mapping[str, str]] = None) -> None:
    settings = load_settings(env)
    logging.basicConfig(level=logging.INFO)
    uvicorn.run(
        create_app(settings),
        host=settings.bind_host,
        port=settings.bind_port,
        ws_max_size=WS_MAX_SIZE_BYTES,
        log_level="info",
    )


if __name__ == "__main__":
    main()

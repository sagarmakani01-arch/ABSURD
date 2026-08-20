"""ABSURD gateway entry point.

Starts FastAPI, initializes the SQLite database, and bridges the internal
event bus to connected WebSocket clients so the frontend can reconstruct
execution history live.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api import all_routers
from app.config import API_TOKEN, CORS_ORIGINS
from app.db import init_db
from app.events import Event, EventType, bus


class WsBridge:
    """Fan-out of internal events to connected WebSocket clients.

    Each client receives the canonical envelope `{type, payload, sequence}`.

    Events may be published from worker threads (sync endpoints run in a
    FastAPI threadpool where there is no running loop), so `broadcast`
    schedules the actual fan-out onto the application's event loop via
    `run_coroutine_threadsafe` rather than calling `asyncio.create_task` at
    publish time.
    """

    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()
        self._lock = asyncio.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None

    def start(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def connect(self, ws: WebSocket) -> None:
        self._clients.add(ws)

    def disconnect(self, ws: WebSocket) -> None:
        self._clients.discard(ws)

    async def _broadcast(self, event: Event) -> None:
        envelope = {
            "type": event.type.value,
            "payload": event.payload,
            "sequence": event.sequence,
        }
        async with self._lock:
            for ws in list(self._clients):
                try:
                    await ws.send_json(envelope)
                except Exception:
                    self._clients.discard(ws)

    def broadcast(self, event: Event) -> None:
        """Schedule fan-out on the app loop. Thread-safe entry point."""
        loop = self._loop
        if loop is None or loop.is_closed():
            return
        future = asyncio.run_coroutine_threadsafe(self._broadcast(event), loop)
        future.add_done_callback(lambda done: done.cancelled() or done.exception())


bridge = WsBridge()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    bridge.start(asyncio.get_running_loop())
    bus.subscribe(bridge.broadcast)
    bus.publish(EventType.SYSTEM_STARTED, {"version": __version__})
    yield


app = FastAPI(title="ABSURD Gateway", version=__version__, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for router in all_routers:
    app.include_router(router, prefix="/api/v1")


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket) -> None:
    """Live event stream. Server sends `{type, payload, sequence}` envelopes."""
    if API_TOKEN:
        token = ws.headers.get("authorization", "").removeprefix("Bearer ")
        if token != API_TOKEN:
            await ws.close(code=1008)
            return
    await ws.accept()
    bridge.connect(ws)
    try:
        while True:
            message = await ws.receive_text()
            # Client messages are handled by the runtime phase; for now,
            # acknowledge to prove bidirectional transport works.
            await ws.send_json({"type": "pong", "payload": {"echo": message}, "sequence": 0})
    except WebSocketDisconnect:
        pass
    finally:
        bridge.disconnect(ws)
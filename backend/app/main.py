"""ABSURD gateway entry point.

Starts FastAPI, initializes the SQLite database, and bridges the internal
event bus to connected WebSocket clients so the frontend can reconstruct
execution history live.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

import hmac
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import __version__
from app.api import all_routers
from app.config import API_TOKEN, CORS_ORIGINS
from app.db import init_db
from app.events import Event, EventType, bus
from app.services import projectors
import app.config as config


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

# Memory projectors attach to the bus at import time (idempotent) so they are
# active in every test process, not only under the lifespan lifecycle, and
# need no event loop of their own.
_projectors_installed = False


def _install_projectors() -> None:
    global _projectors_installed
    if not _projectors_installed:
        projectors.install()
        _projectors_installed = True


_install_projectors()


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

# Bearer-token auth (Phase 13f). Active only when ABSURD_API_TOKEN is set;
# the health endpoint and the API docs stay readable. The token value is
# read per request so tests can flip it without reimporting the app.
_AUTH_EXEMPT_PATHS = {"/health", "/api/v1/health", "/docs", "/openapi.json", "/redoc"}


@app.middleware("http")
async def bearer_auth(request: Request, call_next) -> JSONResponse:
    token = config.API_TOKEN
    if token and request.url.path not in _AUTH_EXEMPT_PATHS:
        if request.headers.get("authorization", "") != f"Bearer {token}":
            return JSONResponse(status_code=401, content={"detail": "unauthorized"})
    return await call_next(request)

for router in all_routers:
    app.include_router(router, prefix="/api/v1")


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket) -> None:
    """Live event stream. Server sends `{type, payload, sequence}` envelopes."""
    if config.API_TOKEN:
        # Browsers cannot set WebSocket headers, so the token is accepted
        # from the Authorization header or the `token` query parameter.
        header_token = ws.headers.get("authorization", "").removeprefix("Bearer ")
        query_token = ws.query_params.get("token", "")
        supplied = query_token or header_token
        if not supplied or not hmac.compare_digest(supplied, config.API_TOKEN):
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
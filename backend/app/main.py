"""ABSURD gateway entry point.

Starts FastAPI, initializes the SQLite database, and bridges the internal
event bus to connected WebSocket clients so the frontend can reconstruct
execution history live.
"""

from __future__ import annotations

import asyncio
import hmac
import json
import time
import uuid as _uuid
from collections import defaultdict, deque
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from app import __version__
from app.api import all_routers
from app.db import SessionLocal, init_db
from app.events import Event, EventType, bus
from app.services import projectors
from app.services.maintenance import run_maintenance
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
    with SessionLocal() as maintenance_session:
        run_maintenance(maintenance_session)
    bridge.start(asyncio.get_running_loop())
    bus.subscribe(bridge.broadcast)
    bus.publish(EventType.SYSTEM_STARTED, {"version": __version__})
    yield


app = FastAPI(title="ABSURD Gateway", version=__version__, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Gateway hardening (Phase 14). One middleware owns: bearer-token auth
# (when ABSURD_API_TOKEN is set), X-Request-ID propagation, per-IP rate
# limiting, and a request body size cap. The health endpoint and the API
# docs stay readable. Config values are read per request so tests can flip
# them without reimporting the app.
_AUTH_EXEMPT_PATHS = {"/health", "/api/v1/health", "/docs", "/openapi.json", "/redoc"}
_rate_buckets: dict[str, deque[float]] = defaultdict(deque)


@app.middleware("http")
async def gateway_middleware(request: Request, call_next) -> JSONResponse:
    path = request.url.path
    public = path in _AUTH_EXEMPT_PATHS

    # 1. X-Request-ID: honour inbound, else generate; echo on the response.
    request_id = request.headers.get("x-request-id") or _uuid.uuid4().hex
    request.state.request_id = request_id

    # 2. Bearer auth.
    token = config.API_TOKEN
    if token and not public:
        if request.headers.get("authorization", "") != f"Bearer {token}":
            return JSONResponse(status_code=401, content={"detail": "unauthorized"})

    # 3. Rate limit (per client IP, sliding one-minute window).
    per_minute = config.RATE_LIMIT_PER_MINUTE
    if per_minute and not public:
        ip = request.client.host if request.client else "unknown"
        now = time.monotonic()
        window = _rate_buckets[ip]
        while window and now - window[0] > 60.0:
            window.popleft()
        if len(window) >= per_minute:
            return JSONResponse(
                status_code=429,
                content={"detail": "rate limit exceeded", "code": "rate_limited"},
            )
        window.append(now)

    # 4. Payload size cap.
    max_bytes = config.MAX_REQUEST_BYTES
    if max_bytes and request.method in {"POST", "PUT", "PATCH"} and not public:
        length = request.headers.get("content-length")
        if length and length.isdigit() and int(length) > max_bytes:
            return JSONResponse(
                status_code=413,
                content={"detail": f"payload exceeds {max_bytes} bytes", "code": "payload_too_large"},
            )

    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response

for router in all_routers:
    app.include_router(router, prefix="/api/v1")


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket) -> None:
    """Live event stream. Server sends `{type, payload, sequence}` envelopes.

    Client → server: `task.create {goal, context?, agent_id?}` runs the task
    and replies `task.accepted {task_id}` (progress streams as the bus fans
    out), `task.cancel {task_id}` requests cancellation, `ping` gets `pong`.
    """
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
            try:
                parsed = json.loads(message)
            except json.JSONDecodeError:
                await ws.send_json({"type": "error", "payload": {"code": "bad_frame", "message": "message must be JSON"}, "sequence": 0})
                continue
            msg_type = parsed.get("type")
            payload = parsed.get("payload") or {}
            if msg_type == "ping":
                await ws.send_json({"type": "pong", "payload": {"timestamp": time.time()}, "sequence": 0})
            elif msg_type == "task.create":
                goal = str(payload.get("goal", "")).strip()
                if not goal:
                    await ws.send_json({"type": "error", "payload": {"code": "missing_goal", "message": "task.create requires a non-empty goal"}, "sequence": 0})
                    continue
                context = payload.get("context") if isinstance(payload.get("context"), dict) else {}
                agent_id = payload.get("agent_id") if isinstance(payload.get("agent_id"), str) else None
                task = await run_in_threadpool(_run_task_via_ws, goal, context, agent_id)
                await ws.send_json({"type": "task.accepted", "payload": {"task_id": task.id}, "sequence": 0})
            elif msg_type == "task.cancel":
                task_id = str(payload.get("task_id", ""))
                if not task_id:
                    await ws.send_json({"type": "error", "payload": {"code": "missing_task_id", "message": "task.cancel requires a task_id"}, "sequence": 0})
                    continue
                task = await run_in_threadpool(_cancel_task_via_ws, task_id)
                if task is None:
                    await ws.send_json({"type": "error", "payload": {"code": "task_not_found", "message": f"no task {task_id}"}, "sequence": 0})
                else:
                    await ws.send_json({"type": "task.cancelled", "payload": {"task_id": task.id, "status": task.status}, "sequence": 0})
    except WebSocketDisconnect:
        pass
    finally:
        bridge.disconnect(ws)


def _run_task_via_ws(goal: str, context: dict[str, object], agent_id: str | None) -> object:
    from app.services.tasks import task_manager

    with SessionLocal() as session:
        task = task_manager.create(session, goal, context, agent_id=agent_id)
        return task_manager.run(session, task)


def _cancel_task_via_ws(task_id: str) -> object | None:
    from app.services.tasks import task_manager

    with SessionLocal() as session:
        return task_manager.cancel(session, task_id)
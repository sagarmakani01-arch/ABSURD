# ABSURD API Gateway

> **Status note (Phase 14):** implemented endpoints live in
> `backend/app/api/routes/` and are verified by `backend/tests/`. Implemented
> set: `health`, `events`, `tasks` (POST `/tasks`, GET `/tasks`,
> GET `/tasks/{id}`, POST `/tasks/{id}/cancel`, GET `/executions`), `tools`
> (POST/GET `/tools`, GET `/tools/{id}`, lifecycle verbs `/verify`, `/activate`,
> `/reject`, `/deprecate`, and `/disable` + `/enable`), `capabilities`
> (GET `/capabilities`), `agents` (GET/POST `/agents`), `evaluations`
> (POST `/evaluations`), `memory` (`/memory/experience`, `/memory/graph`,
> `/memory/graph/coverage-gaps`, `/memory/tools-usage`), `evolution`
> (`metrics`, `events`, `revisions`, `promotions`). The gateway also applies
> X-Request-ID, opt-in per-IP rate limiting, and payload-size caps; the WS
> bridge speaks the JSON protocol below.

FastAPI gateway — the only entry point for the ABSURD UI. Exposes synchronous REST endpoints and a WebSocket endpoint for streaming/event delivery. It owns auth, request validation, and fan-out to the Agent Engine, Tool System, Memory System, and Evolution Loop.

## 1. Base URL & Conventions

- REST base path: `/api/v1`
- WebSocket endpoint: `/ws`
- All request/response bodies are JSON (`application/json`).
- All bodies and responses are validated with Pydantic schemas.
- Errors use RFC 7807-style problem details: `{"detail": "message", "code": "string"}`.
- Every request carries a `X-Request-ID`; the gateway generates one if absent and propagates it to all downstream events and logs.

## 2. REST Endpoints

### Tasks

| Method | Path | Description |
|---|---|---|
| POST | `/tasks` | Create a task. Body: `TaskCreate {goal, context?, agent_id?}` → `Task {id, status, steps[], result?, error?}`. |
| GET | `/tasks/{task_id}` | Fetch task status and current step. |
| POST | `/tasks/{task_id}/cancel` | Request cancellation; respected between steps. |
| GET | `/tasks` | List tasks with optional `?status=` filter and `?limit=`/`?offset=` pagination. |

### Tools & Capabilities

| Method | Path | Description |
|---|---|---|
| GET | `/tools` | List registered tools. `?tag=` and `?q=` filters supported. |
| GET | `/tools/{tool_id}` | Tool detail: schema, provenance (generated vs manual), confidence, usage count. |
| POST | `/tools/{tool_id}/disable` | Disable a tool so the planner stops using it. |
| GET | `/capabilities` | Aggregate view of tool coverage per capability domain (drives Capability Detector). |

### Agents

| Method | Path | Description |
|---|---|---|
| GET | `/agents` | List agent instances (planner/reasoner configs). |
| POST | `/agents` | Create an agent configuration (planner strategy, reasoning depth). |

### Memory

| Method | Path | Description |
|---|---|---|
| GET | `/memories/tools` | Query Tool Memory. |
| GET | `/memories/experiences` | Query Experience Memory, `?status=failed` etc. |
| GET | `/memories/knowledge` | Query Knowledge Graph; `?node=` returns neighborhood subgraph. |
| POST | `/memories/knowledge/query` | Graph query body: `{start_node, depth}`. |

### Evolution

| Method | Path | Description |
|---|---|---|
| GET | `/evolution/events` | Append-only event log of evolution activities (`?event_type=` filter). |
| GET | `/evolution/metrics` | Aggregate stats: tools generated, registered, failed, loop iterations, mean time-to-capability. |

### System

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Liveness + dependency status (`{status: "ok", deps: {...}}`). |
| GET | `/openapi.json` | Generated OpenAPI spec (FastAPI default). |

## 3. WebSocket Protocol

Endpoint: `ws://<host>/ws`

Client messages are JSON envelopes `{"type": "...", "payload": {...}}`.
Bare text frames are answered with an `error` frame (`bad_frame`).

### Client → Server Messages

| `type` | Payload | Description |
|---|---|---|
| `task.create` | `{goal, context?, agent_id?}` | Submit a new task; runs it and replies `task.accepted` + `task.finished`. |
| `task.cancel` | `{task_id}` | Cancel a running task; replies `task.cancelled`. |
| `ping` | `{}` | Keepalive; gateway replies `pong`. |

Unknown message types → `error {"code": "unknown_message"}`; malformed payloads
→ `error` frames (e.g. `missing_goal`, `missing_task_id`).

### Server → Client Messages

Every message uses the envelope `{"type": "...", "payload": {...}}`.

| `type` | Payload | Description |
|---|---|---|
| `task.accepted` | `{task_id}` | Task accepted into the pipeline. |
| `task.update` | `{task_id, status}` | Lifecycle update per transition (including `task.finished` on completion). |
| `task.cancelled` | `{task_id, status}` | Cancellation acknowledged. |
| `task_not_found` | `{task_id}` | Cancellation requested for an unknown task. |
| `error` | `{code, message}` | Protocol or task error. |
| `pong` | `{timestamp}` | Keepalive reply. |

## 4. Authentication & Gateway Hardening

- v1: static bearer token (env `ABSURD_API_TOKEN`), enforced by an HTTP
  middleware on every REST route and at WS accept (Phase 13f). REST requires
  `Authorization: Bearer <token>`; the WebSocket accepts the same header or a
  `token` query parameter (browsers cannot set WS headers). `/health`,
  `/api/v1/health`, and the API docs are exempt. Empty token = auth disabled.
- Future: JWT with scopes (`task:read`, `task:write`, `tool:admin`, `memory:read`).
- All auth failures → `401 {"detail": "unauthorized", "code": "auth.unauthorized"}` (WS: close 1008).
- `X-Request-ID`: honored when the client sends one, generated otherwise;
  echoed on the response and propagated as `state.request_id` to all
  downstream events via the gateway middleware.
- Rate limiting (Phase 14): sliding 60-second window per client IP, opt-in via
  `ABSURD_RATE_LIMIT_PER_MINUTE` (default `0` = disabled). Exceeding the
  window → `429 {"detail": ..., "code": "rate_limited"}`. `/health` and
  `/api/v1/health` are exempt.
- Payload cap (Phase 14): requests with a `Content-Length` above
  `ABSURD_MAX_REQUEST_BYTES` (default 262144) → `413
  {"detail": ..., "code": "payload_too_large"}`.
- Custom status codes returned by the application layer: `409
  capability_unfillable` (generation refused for a proven-unfillable gap),
  `422 unsupported_strategy` (agent planner strategy not implemented),
  `404 task_not_found`, `422 terminal_task` (cancelling a finished task).

## 5. Gateway Responsibilities (not the core logic)

- Validation of incoming payloads against Pydantic schemas.
- Authentication, request-id propagation, rate limiting, and payload caps.
- Routing: dispatch task work to the Agent Engine; fan out events to connected WS clients via an in-process event bus.
- No business logic beyond orchestration — planner, tooling, memory, evolution all live in `core/`.

## 6. Example: Create Task (REST)

```
POST /api/v1/tasks
{
  "goal": "build a markdown table from this CSV",
  "context": {"file_url": "..."}
}

202 Accepted
{
  "id": "task_01J...",
  "status": "accepted",
  "steps": []
}
```

Subsequent progress arrives over the WebSocket as `task.update` messages using the same `task_id`.

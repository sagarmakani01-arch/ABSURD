# ABSURD API Gateway

> **Status note (Phase 11):** endpoints below marked *(implemented)* exist in
> `backend/app/api/routes/`. All others are target spec — the gateway returns
> 404 until a later phase. Implemented set: `health`, `events`, `tasks`
> (POST `/tasks`, GET `/tasks`, GET `/tasks/{id}`, GET `/executions`), `tools`
> (POST `/tools`, GET `/tools`, GET `/tools/{id}`, and the lifecycle verbs
> `/verify`, `/activate`, `/reject`, `/deprecate`), `evaluations`
> (POST `/evaluations`), `memory` (`/memory/experience`, `/memory/graph`,
> `/memory/graph/coverage-gaps`, `/memory/tools-usage`), `evolution`
> (`metrics`, `events`, `revisions`, `promotions`).

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

### Client → Server Messages

| `type` | Payload | Description |
|---|---|---|
| `task.create` | `{goal, context?, agent_id?}` | Submit a new task; gateway replies with `task.accepted`. |
| `task.cancel` | `{task_id}` | Cancel running task. |
| `subscribe.tool` | `{tool_id}` | Subscribe to execution/registration events for a tool. |
| `ping` | `{}` | Keepalive; gateway replies `pong`. |

### Server → Client Messages

Every message uses the envelope `{"type": "...", "payload": {...}}`.

| `type` | Payload | Description |
|---|---|---|
| `task.accepted` | `{task_id}` | Task accepted into the pipeline. |
| `task.update` | `{task_id, status, current_step?, progress?}` | Streamed progress (one per step transition). |
| `task.result` | `{task_id, result, tool_trace[]}` | Final result with the list of tools used. |
| `tool.executing` | `{tool_id, task_id}` | A tool began executing. |
| `tool.registered` | `{tool_id, name, description, confidence}` | A generated tool was promoted to the registry. |
| `evolution.event` | `{event_id, event_type, timestamp, payload}` | Evolution loop activity (see evolution-loop.md). |
| `error` | `{code, message, request_id}` | Protocol or task error. |
| `pong` | `{timestamp}` | Keepalive reply. |

## 4. Authentication

- v1: static bearer token (env `ABSURD_API_TOKEN`), enforced via dependency on every REST route and WS accept.
- Future: JWT with scopes (`task:read`, `task:write`, `tool:admin`, `memory:read`).
- All auth failures → `401 {"detail": "unauthorized", "code": "auth.unauthorized"}`.

## 5. Gateway Responsibilities (not the core logic)

- Validation of incoming payloads against Pydantic schemas.
- Authentication and request-id propagation.
- Routing: dispatch task work to the Agent Engine; fan out events to connected WS clients via an in-process event bus.
- Rate limiting (per token/IP) and payload size caps on task bodies.
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

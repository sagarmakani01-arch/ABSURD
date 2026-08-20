# ABSURD — System Architecture

> **Status note (Phase 12):** this document is the target/design spec. The
> implemented matrix is in `README.md`. Tool generation is implemented for the
> deterministic template strategy only; the security sandbox and real tool
> execution are **not implemented** — their contracts exist and every API
> surface for them returns structured "not implemented" responses.

## 1. Overview

ABSURD is a self-evolving AI agent platform. It combines a React + TypeScript frontend, a FastAPI gateway, an agent engine, a tool system with dynamic tool generation, a multi-tier memory system, and an evolution loop that turns execution outcomes into improved capabilities.

The defining property of ABSURD is the **Evolution Loop**: tools that succeed are registered into the system's permanent capabilities; tools that fail are analyzed and fed back into the reasoner/planner so the next attempt is better.

## 2. System Context

```
                         ┌─────────────────────────┐
                         │       ABSURD UI        │
                         │ React + TypeScript      │
                         │ Landing / Dashboard     │
                         └────────────┬────────────┘
                                      │
                              WebSocket / REST
                                      │
                         ┌────────────▼────────────┐
                         │       API GATEWAY       │
                         │        FastAPI           │
                         └────────────┬────────────┘
                 ┌────────────────────┼───────────────────┐
                 ▼                    │                   ▼
          ┌─────────────┐     ┌──────────────┐    ┌──────────────┐
          │   AGENT     │     │ TOOL SYSTEM  │    │   MEMORY     │
          │   ENGINE    │     │              │    │   SYSTEM     │
          └──────┬──────┘     └──────┬───────┘    └──────┬───────┘
                 │                   │                   │
       ┌─────────┼─────────┐         │          ┌────────┼────────┐
       ▼         ▼         ▼         ▼          ▼        ▼        ▼
    Planner  Capability  Reasoner  Registry  Tool     Experience Knowledge
             Detector                       Memory     Memory    Graph
                 │
                 ▼
        ┌──────────────────┐
        │ TOOL GENERATOR   │
        └────────┬─────────┘
                 │
                 ▼
        ┌──────────────────┐
        │ SECURITY         │
        │ SANDBOX          │
        └────────┬─────────┘
                 │
                 ▼
        ┌──────────────────┐
        │ TOOL EXECUTION   │
        └────────┬─────────┘
                 │
          ┌──────┴───────┐
          ▼              ▼
       SUCCESS          FAILURE
          │              │
          ▼              ▼
      REGISTER       ANALYZE
          │              │
          └──────┬───────┘
                 ▼
            EVOLUTION LOOP
```

## 3. Component Responsibilities

| Component | Responsibility |
|---|---|
| ABSURD UI | Landing page, dashboard, live run monitoring via WebSocket, REST-driven CRUD for tools/memories/agents. |
| API Gateway | Single entry point. REST for synchronous ops, WebSocket for streaming/events. Auth, routing, validation, fan-out. |
| Agent Engine | Decomposes goals into plans (`Planner`), detects which capabilities exist (`Capability Detector`), reasons over results (`Reasoner`). |
| Tool System | Registry of known/generated tools; `Tool Generator` synthesizes new tools for gaps; sandboxed execution. |
| Memory System | Persistent knowledge: `Tool Memory`, `Experience Memory`, `Knowledge Graph`. |
| Security Sandbox | Isolates generated tool code — subprocess/container, capability capping, allow-lists, secrets handling. |
| Evolution Loop | Success → register tool (promote to capability). Failure → analyze → feed lessons back to reasoner/planner. |

## 4. Key Architectural Decisions

1. **REST + WebSocket hybrid** — REST for request/response, WebSocket for live task progress, logs, and evolution events (event `type` discriminator).
2. **FastAPI gateway** — async-native, easy WebSocket support, Pydantic validation as contract enforcement between UI and core.
3. **Code-generated tools** — the Tool Generator produces tool definitions (schema + implementation) that are validated by the Sandbox before any execution.
4. **Memory as multiple stores** — separate concerns: what tools exist (Tool Memory), what happened (Experience Memory), and how things relate (Knowledge Graph).
5. **Evolution is event-driven** — tool success/failure emits events that trigger registration or analysis asynchronously, keeping the request path fast.

## 5. Primary Data Flow (Task Execution)

1. UI sends task via WebSocket message or REST `POST /tasks`.
2. Gateway validates and emits `task.created`.
3. Agent Engine `Planner` decomposes the goal into steps.
4. `Capability Detector` maps each step to registered tools (from Tool Memory/Registry); gaps are noted.
5. Gap → `Tool Generator` synthesizes candidate tool; `Security Sandbox` validates and executes it.
6. Tool result returns to `Reasoner`.
7. On success: `Register` → tool promoted, Tool Memory/Knowledge Graph updated, `tool.registered` event emitted.
8. On failure: `Analyze` → failure root-causing, lessons stored to Experience Memory, reasoner adjusts, evolution event emitted.
9. Final task result streamed back to UI over WebSocket.

## 6. Communication Contracts

- **REST**: `POST /tasks`, `GET /tasks/{id}`, `GET /tools`, `POST /evaluations`,
  `GET /memory/experience`, `GET /memory/graph`, `GET /memory/graph/coverage-gaps`,
  `GET /memory/tools-usage`, `GET /evolution/metrics`,
  `POST /evolution/revisions`, `POST /evolution/promotions`,
  `GET /evolution/events`, `GET /events` (full list in `api-gateway.md`).
- **WebSocket** `/ws`: client→server `task.create`, `task.cancel`; server→client `task.update`, `tool.registered`, `evolution.event`, `error`.
- All payloads are JSON. All REST bodies validated via Pydantic schemas. WS events carry a `type` + `payload` envelope.

## 7. Directory Layout

Implemented layout (see also `README.md`):

```
backend/
  app/
    api/routes/          # health, events, tasks, tools, evaluation,
                         # memory, evolution routers
    core/agent/          # planner, detector, reasoner, engine
    core/tools/          # tool model, registry lifecycle
    services/            # memory stores, event projectors, evolution loop
    db.py / models.py    # engine, session, SQLAlchemy models
    main.py              # FastAPI app, WS bridge, projector install
  tests/                 # pytest suite (43 passing)
frontend/
  src/app/               # /app shell, AppLayout
  src/pages/app/         # Overview, Tools, ToolDetail, Tasks, Experiments,
                         # Memory, Evaluation, System
  src/lib/               # api client, hooks, useEventStream
docs/                    # module specs + architecture audit
```

Planned additions from the original design (not yet created): a dedicated
sandbox module, tool generator, and execution worker — the shapes are specced
in `tool-system.md`.

## 8. Reliability & Observability

- Gateway and core services log structured JSON with a shared `request_id` propagated from gateway to evolution events.
- Evolution events are persisted (append-only) for replay and audit.
- The Knowledge Graph is the source of truth for relationships; stores are eventually consistent via the same event stream.
- Sandbox failures never crash the gateway: generated code runs in an isolated process/container with hard limits (CPU, memory, wall-clock, network off by default).

## 9. Docs Index

- [API Gateway](api-gateway.md) — endpoints, WebSocket protocol, auth.
- [Agent Engine](agent-engine.md) — planner, capability detection, reasoning.
- [Tool System](tool-system.md) — registry, generator, sandbox, execution.
- [Memory System](memory-system.md) — three stores and their schemas.
- [Evolution Loop](evolution-loop.md) — register/analyze pipeline and event flow.
- [Frontend](frontend.md) — UI structure, WS/REST client usage.

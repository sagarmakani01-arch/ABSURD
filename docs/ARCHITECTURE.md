# GENESIS — System Architecture

## 1. Overview

GENESIS is a self-evolving AI agent platform. It combines a React + TypeScript frontend, a FastAPI gateway, an agent engine, a tool system with dynamic tool generation, a multi-tier memory system, and an evolution loop that turns execution outcomes into improved capabilities.

The defining property of GENESIS is the **Evolution Loop**: tools that succeed are registered into the system's permanent capabilities; tools that fail are analyzed and fed back into the reasoner/planner so the next attempt is better.

## 2. System Context

```
                         ┌─────────────────────────┐
                         │       GENESIS UI        │
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
| GENESIS UI | Landing page, dashboard, live run monitoring via WebSocket, REST-driven CRUD for tools/memories/agents. |
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

- **REST**: `POST /tasks`, `GET /tasks/{id}`, `GET /tools`, `GET /agents`, `GET /memories`, `GET /evolution/events` (full list in `api-gateway.md`).
- **WebSocket** `/ws`: client→server `task.create`, `task.cancel`; server→client `task.update`, `tool.registered`, `evolution.event`, `error`.
- All payloads are JSON. All REST bodies validated via Pydantic schemas. WS events carry a `type` + `payload` envelope.

## 7. Directory Layout (Target)

```
apps/
  ui/                 # React + TypeScript frontend (Vite)
    src/pages/        # Landing, Dashboard
    src/ws/           # WebSocket client
    src/api/          # REST client
  gateway/            # FastAPI app
    app/routes/       # REST + WS routers
    app/schemas/      # Pydantic contracts
core/
  agent/              # Planner, CapabilityDetector, Reasoner
  tools/              # Registry, ToolGenerator, Executor
  memory/             # tool_memory, experience_memory, knowledge_graph
  sandbox/            # SecuritySandbox
  evolution/          # evolution loop handlers
```

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

# ABSURD — A Self-Extending Agent Runtime

ABSURD is a research project into **self-extending agents**: an agent that
runs real tasks, discovers when it lacks a capability, and grows its own tool
registry to cover the gaps. Every claim here is either implemented and
tested or explicitly labelled as not built yet — there is no simulated
intelligence.

## PROBLEM

Foundation models can *plan* but their capability surface is static. When a
task needs a tool the agent does not have, a "smart" agent silently improvises
or fails opaquely. Two hard questions are usually hand-waved:

1. **Honesty** — how does the system know it cannot do something, and how does
   it say so in machine-readable, structured terms?
2. **Self-extension** — how does a capability deficit become a permanent,
   verified addition to the agent's own tool set, with a lifecycle, quality
   gate, and rollback?

Most demo systems fake the second by hiding the first. ABSURD treats failure
as first-class data and only promotes a tool through a real, deterministic
lifecycle.

## IDEA

ABSURD decomposes the problem into distinct, independently verifiable layers:

- **Deterministic agent runtime** — a task goes `analyze → plan → detect →
  verdict`. The planner splits a goal into steps; the capability detector maps
  each step to registered tools using schema-level type compatibility; the
  reasoner emits an honest verdict: `COVERED`, `PARTIAL_CAPABILITY`, or
  `NO_CAPABILITY` — the last two with a structured `gap_spec` describing
  exactly what tool is missing.
- **Tool registry lifecycle** — tools move `DRAFT → VERIFIED → REGISTERED → DEPRECATED`
  (or `REJECTED`). Promotion is gated on structural quality checks and schema
  sanity. Registered tools contribute `tool ─enables→ capability` edges.
- **Memory as a projection of the event stream** — the system of record is a
  typed event bus; tool memory, experience memory, and a knowledge graph are
  projections of it. Nothing in a request handler writes memory directly.
- **Evolution loop** — failures are classified deterministically and write
  `blocks` edges plus lessons; gap-close rate, failure-by-kind, and revision
  activity are computed as measurable metrics. Revision/versioning exists as a
  real, guarded pipeline — and honestly refuses to run until the generator it
  needs is built.

What ABSURD does **not** fake: there is no LLM in the loop today. Tool
generation (`generation_available: false`), the security sandbox, and real
tool execution are later phases. The API surface for them already exists and
returns structured "not implemented yet" responses rather than pretending.

## ARCHITECTURE

```
                ABSURD UI (React + TS, Vite)
                     │  /api/v1 REST + /ws events
                     ▼
                API GATEWAY (FastAPI)
                     │  typed event bus (WS fan-out)
        ┌────────────┼───────────────┬──────────────────┐
        ▼            ▼               ▼                  ▼
   AGENT RUNTIME  TOOL REGISTRY  MEMORY SYSTEM     EVOLUTION LOOP
   planner        lifecycle +     experience mem    failure classify
   detector       capabilities    knowledge graph   quarantine
   reasoner       structural gate tool memory       revisions (gated)
```

- `backend/app/api/` — FastAPI routers (health, events, tasks, tools,
  evaluation, memory, evolution) + WebSocket bridge.
- `backend/app/core/agent/` — planner, schema-based capability detector,
  reasoner, engine. Fully deterministic.
- `backend/app/core/tools/` — tool model + registry with transition rules.
- `backend/app/services/` — memory stores, event projectors, evolution loop.
- `backend/app/models.py` — SQLAlchemy models (tasks, tools, executions,
  experiences, knowledge-graph edges).
- `frontend/src/` — landing page plus `/app` shell: Overview, Tools, Tasks,
  Experiments, Memory, Evaluation, System, with a live event stream
  (`useEventStream`, reconnect + heartbeat, 200-event buffer).

Design rationale and the historical decision log live in
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## SECURITY

The security posture is conservative because the dangerous parts are not built
yet and the design says so:

- No generated code runs anywhere. Sandbox (subprocess/container isolation,
  resource caps, network-off default, AST policy checks) is specced in
  [`docs/tool-system.md`](docs/tool-system.md) and marked **not implemented**.
- Tool *source code* is accepted by the registry as metadata only; it is never
  evaluated, imported, or executed.
- WebSocket bridge authenticates against `API_TOKEN` (empty = disabled
  locally; see `backend/.env.example`).
- Secrets never enter tools: executions, when they exist, receive only the
  caller-provided inputs.
- Quarantine and version gates already enforce lifecycle invariants
  server-side (e.g. a revision cannot be promoted before a completed revision
  exists).

## STATUS

| Capability | State |
|---|---|
| Task lifecycle (`CREATED → FAILED/COMPLETED`) | Implemented & tested |
| Deterministic planning + schema capability detection | Implemented & tested |
| Partial/gap verdicts with structured `gap_spec` | Implemented & tested |
| Tool registry lifecycle + structural gate | Implemented & tested |
| Experience memory, knowledge graph, tools memory | Implemented & tested |
| Evolution metrics, failure analysis, quarantine | Implemented & tested |
| Revision/versioning pipeline (guarded) | Implemented & gated |
| Tool generation (deterministic template strategy) | Implemented & tested |
| LLM-assisted tool / revision generation | **Not implemented** (honest 409s) |
| Security sandbox + real tool execution | **Not implemented** (specced only) |

Backend test suite: **47 passed** (`backend/tests`). Frontend: typecheck,
lint and build green.

## GETTING STARTED

Backend (Python 3.14):

```sh
cd backend
python -m venv .venv
.venv\Scripts\activate        # PowerShell
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Frontend (Node 22+, npm):

```sh
cd frontend
npm install
npm run dev
```

Open http://localhost:8000 for the app shell and `/api/v1/health` for the
gateway. Tests: `cd backend && python -m pytest` from `backend/`.

## ROADMAP

- Phases 1–5: foundation — project scaffold, gateway + health, WebSocket event
  bridge, application shell. **Done.**
- Phase 6: deterministic agent runtime. **Done.**
- Phase 7: tool registry lifecycle. **Done.**
- Phase 8: schema-based capability detection. **Done.**
- Phase 9: memory system, evaluation pipeline, evolution loop. **Done.**
- Phase 10: revision/versioning loop with honest gating. **Done.**
- Phase 11: this documentation. **Done.**
- Frontend wiring: app-shell modules now consume the live lifecycle (tasks,
  registry, memory, evaluation, evolution); placeholder panels removed.
  **Done.**
- Phase 12: deterministic tool generation (template strategy) — tasks seed
  DRAFT candidates for gaps; registering a candidate closes the loop.
  **Done.**
- Next: sandboxed execution (runs a tool's tests for real behavioral
  verification), then LLM-assisted generation and semantic matching (docs per
  module).

## DOCS

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — system architecture.
- [`docs/agent-engine.md`](docs/agent-engine.md) — planner, detector, reasoner.
- [`docs/tool-system.md`](docs/tool-system.md) — registry, generator, sandbox.
- [`docs/memory-system.md`](docs/memory-system.md) — three memory stores.
- [`docs/evolution-loop.md`](docs/evolution-loop.md) — register/analyze loop.
- [`docs/api-gateway.md`](docs/api-gateway.md) — endpoints and WS protocol.
- [`docs/frontend.md`](docs/frontend.md) — UI structure and client usage.
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

What ABSURD does **not** fake: all AI-dependent paths ship as real, tested
transports that are **honestly conditional**. Tool generation and revisions
use an LLM when `ABSURD_LLM_*` credentials are configured, and otherwise
degrade to the deterministic template strategy with a structured
`generation_available: false` signal — never a pretend model. The same
pattern holds for the embedding matching tier (`ABSURD_EMBEDDINGS_*`).

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
- `backend/app/core/agent/` — planner, schema-based capability detector
  (with an optional semantic embedding tier), reasoner, engine (executes
  covered steps in the sandbox). Fully deterministic.
- `backend/app/core/tools/` — tool model + registry with transition rules.
- `backend/app/services/` — sandbox (AST policy + subprocess execution),
  tool generator (template + LLM strategy), memory stores, event projectors,
  evolution loop, semantic matching.
- `backend/app/models.py` — SQLAlchemy models (tasks, tools, executions,
  experiences, knowledge-graph edges).
- `frontend/src/` — landing page plus `/app` shell: Overview, Tools, Tasks,
  Experiments, Memory, Evaluation, System, with a live event stream
  (`useEventStream`, reconnect + heartbeat, 200-event buffer).

Design rationale and the historical decision log live in
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## SECURITY

The security posture is conservative. The sandbox runs tool code for real,
but refuses everything it cannot prove safe:

- Sandbox (`backend/app/services/sandbox.py`): every execution runs in a
  fresh `python -I` subprocess with a throwaway working directory. An AST
  policy check rejects `eval`/`exec`/`compile`/`__import__`, all imports,
  `open`, dunder access, and shadowed attribute tricks **before** the
  subprocess starts; the same policy gates tool source and stored tests at
  registration time. The behavioral gate (`POST /evaluations`) executes the
  tool's own tests in the sandbox; timeout (default 30s) and output-size caps
  apply. Spec history: [`docs/tool-system.md`](docs/tool-system.md).
- Tool code runs only inside the sandbox — never imported or evaluated in the
  gateway process. Executions receive only the caller-provided inputs; result
  output must deserialize against the tool's declared `output_schema`.
- REST and WebSocket routes authenticate against `ABSURD_API_TOKEN` when set
  (empty = disabled locally). REST accepts `Authorization: Bearer ...`;
  the WS accepts the same header or a `token` query parameter (browsers
  cannot set WS headers). `/health` and the API docs stay public.
- Quarantine and version gates enforce lifecycle invariants server-side
  (e.g. a revision cannot be promoted before a completed revision exists).

## STATUS

| Capability | State |
|---|---|
| Task lifecycle (`CREATED → FAILED/COMPLETED`) | Implemented & tested |
| Deterministic planning + schema capability detection | Implemented & tested |
| Partial/gap verdicts with structured `gap_spec` | Implemented & tested |
| Semantic embedding matching tier (optional, schema stays authoritative) | Implemented & gated on `ABSURD_EMBEDDINGS_*` |
| Tool registry lifecycle + structural gate | Implemented & tested |
| Experience memory, knowledge graph, tools memory | Implemented & tested |
| Evolution metrics, failure analysis, quarantine (real, on execution failures) | Implemented & tested |
| Revision/versioning pipeline | Implemented & gated on LLM credentials |
| Tool generation (template strategy) | Implemented & tested |
| LLM-assisted tool / revision generation | Implemented & tested (with fake transport) — degraded to template when unconfigured |
| Security sandbox + real tool execution | Implemented & tested |
| Behavioral verification gate (`POST /evaluations`) | Implemented & tested |
| REST + WS bearer auth | Implemented & tested (disabled when token empty) |
| Gateway hardening (X-Request-ID, opt-in rate limit, payload cap) | Implemented & tested (rate limit off by default) |
| WS task lifecycle (`ping`, `task.create`, `task.cancel`) | Implemented & tested |
| Task cancellation (`POST /tasks/{id}/cancel`) | Implemented & tested |
| Tool disable/enable + `GET /capabilities` coverage | Implemented & tested |
| Agent configurations (planner strategy `split`/`flat`, retry budget) | Implemented & tested (other strategies reject with `unsupported_strategy`) |
| Engine retry/re-plan loop with `PLAN_REVISED` events | Implemented & tested |
| Composition matching (chained covers A→B) | Implemented & tested |
| Unfillable-gap honesty (thresholded refusal, `capability_unfillable`) | Implemented & tested |
| Maintenance sweeps: confidence decay, retention, KG pruning, PII redaction | Implemented & tested |

Backend test suite: **107 passed** (`backend/tests`). Frontend: typecheck,
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

All configuration is env-driven (see `backend/.env.example`); the only
required setting is none — ABSURD runs fully configured, with the LLM,
embedding and auth tiers simply disabled:

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
- Phase 13: sandboxed tool execution with real outcomes, behavioral
  verification gate, LLM-assisted generation/revisions, semantic embedding
  matching, and REST/WS bearer auth. **Done.**
- Phase 14: gateway hardening (X-Request-ID, opt-in rate limiting, payload
  caps), WS task lifecycle (`task.create`/`task.cancel`), task cancellation,
  tool disable/enable + capability coverage view, agent configurations
  (strategy + retry budget), engine retry/re-plan loop, composition matching
  for chained covers, unfillable-gap honesty (thresholded refusal),
  maintenance sweeps (confidence decay, retention, KG pruning, PII
  redaction). **Done.**

## DOCS

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — system architecture.
- [`docs/agent-engine.md`](docs/agent-engine.md) — planner, detector, reasoner.
- [`docs/tool-system.md`](docs/tool-system.md) — registry, generator, sandbox.
- [`docs/memory-system.md`](docs/memory-system.md) — three memory stores.
- [`docs/evolution-loop.md`](docs/evolution-loop.md) — register/analyze loop.
- [`docs/api-gateway.md`](docs/api-gateway.md) — endpoints and WS protocol.
- [`docs/frontend.md`](docs/frontend.md) — UI structure and client usage.
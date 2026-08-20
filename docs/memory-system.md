# ABSURD Memory System

Three persistent stores that back every other component. Data in all three is written from the same event stream, keeping the stores mutually consistent.

```
                 ┌───────────────────────────────┐
                 │         EVENT STREAM          │
                 └───────┬────────┬────────┬─────┘
                         ▼        ▼        ▼
              ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
              │    TOOL      │ │ EXPERIENCE   │ │ KNOWLEDGE    │
              │    MEMORY    │ │ MEMORY       │ │ GRAPH        │
              └──────────────┘ └──────────────┘ └──────────────┘
```

## 1. Tool Memory

- **Purpose:** persisted store of the Tool Registry and tool-level metadata.
- **Records:** tool definitions (schemas, provenance, status), confidence/success-rate aggregates.
- **Reads:** Capability Detector coverage checks, `GET /tools` API.
- **Writes:** on `tool.registered`, `tool.updated` (confidence/success rate from the Evolution Loop).

## 2. Experience Memory

- **Purpose:** time-series of what actually happened — tasks, step plans, tool executions, outcomes.
- **Record shape (append-only):**

```json
{
  "id": "exp_01H...",
  "task_id": "task_01G...",
  "kind": "task" | "step" | "tool_execution",
  "input": {...},          // goal / step spec / tool call
  "outcome": "success" | "failure" | "partial",
  "result": {...},         // or error detail
  "lessons": ["..."],      // filled by Reasoner / Analyze
  "timestamp": "..."
}
```

- **Reads:** Planner (`memory-guided` seeding), Reasoner (similar past failures), Evolution Loop analytics (`GET /evolution/metrics`).
- **Queries:** filter by kind, outcome, tool_id, similarity search on `input` for "tasks like this one".

## 3. Knowledge Graph

- **Purpose:** semantic relationships between goals, capabilities, tools, and failure patterns.
- **Nodes:** `Goal`, `Capability`, `Tool`, `FailurePattern`, `Resource(s)`.
- **Edges:**
  - `Tool ─enables→ Capability`
  - `Capability ─covers→ Goal`
  - `FailurePattern ─blocks→ Goal`
  - `Tool ─satisfies→ FailurePattern` (a fix exists)
  - `Tool ─depends_on→ Resource`
- **Writes:** `tool.registered` (enables + covers edges), `evolution.event` with `capability.gap` (blocks edge), `failure.analyzed` (satisfies edge).
- **Reads:** Capability Detector composition checks (multi-hop paths), dashboard "capability coverage" panel, gap discovery queries like "which goals have no covering capability".
- Backend options: property graph (e.g., Neo4j or networkx in-process for v1).

## 4. Consistency Model

- All writes flow through the event stream → each store is a projection of events.
- Stores are eventually consistent; the stream is the system of record.
- No store writes happen directly from request handlers; handlers only emit events.

## 5. Retention & Privacy

- Tool Memory: retention of disabled/quarantined tools configurable (default 180 days).
- Experience Memory: full retention by default; PII fields marked via schema annotations and redacted at write time.
- Knowledge Graph: nodes with no edge for 90 days are pruned.
# GENESIS Frontend (UI)

React + TypeScript landing page and dashboard. Communicates with the API Gateway over REST (synchronous ops) and WebSocket (live events).

## 1. Tech Stack

- React 18+, TypeScript, Vite (build/dev server)
- State/data: TanStack Query for REST, native WebSocket client wrapped in a typed hook
- Routing: React Router (landing `/`, dashboard `/dashboard`)
- Styling: CSS modules or Tailwind (decide at scaffold time; no external UI kit required)

## 2. Pages

### Landing (`/`)

- Product pitch, architecture summary, "Open Dashboard" CTA.
- Live status strip: single WebSocket light showing gateway health (`/health` poll + WS connect state).
- Fetches nothing heavy — static content plus health check.

### Dashboard (`/dashboard`)

- **Agents panel** — list agents, create agent config (`POST /agents`).
- **Tasks panel** — create task, list tasks (`GET /tasks`), click into task detail with live step stream via WS.
- **Tools panel** — `GET /tools`, tool detail drawer (schemas, confidence, success rate), disable action.
- **Memory panel** — `GET /memories/*` query UI for experiences and knowledge graph neighborhood explorer.
- **Evolution panel** — `GET /evolution/events` + `GET /evolution/metrics`; live event log appended in real time from WS `evolution.event` messages.

## 3. WebSocket Client

`src/ws/` — typed client hook (`useGenesisSocket`):

- Auto-reconnect with exponential backoff (1s → 30s cap), heartbeat `ping` every 25s.
- Envelope types shared with the gateway (`src/types/ws.ts`): a discriminated union on `type`.
- Subscription model: components subscribe to event `type`s; one socket shared app-wide.
- On disconnect, dashboard shows stale-state banner; on reconnect, REST refetch reconciles missed events.

Key event types consumed:

```ts
type ServerEvent =
  | { type: "task.accepted"; payload: { taskId: string } }
  | { type: "task.update"; payload: { taskId: string; status: TaskStatus; currentStep?: string; progress?: number } }
  | { type: "task.result"; payload: { taskId: string; result: unknown; toolTrace: ToolRef[] } }
  | { type: "tool.executing"; payload: { toolId: string; taskId: string } }
  | { type: "tool.registered"; payload: { toolId: string; name: string; description: string; confidence: number } }
  | { type: "evolution.event"; payload: EvolutionEvent }
  | { type: "error"; payload: { code: string; message: string; requestId: string } };
```

## 4. REST Client

`src/api/` — typed fetch wrappers per resource (tasks, tools, agents, memories, evolution, health). Base URL from `VITE_API_BASE`. Uses TanStack Query keys: `["tasks"]`, `["tools"]`, `["memories","experiences"]`, `["evolution","metrics"]`, etc. Mutations invalidate the matching keys.

## 5. Data Flow Examples

**Create a task (live progress):**

1. `POST /api/v1/tasks` → task id.
2. Socket emits `task.update` events → task detail subscribes and renders step list.
3. Terminal `task.result` event → detail panel shows result + tool trace.

**Watch evolution live:**

1. On mount: `GET /evolution/metrics` (initial numbers) + socket subscription to `evolution.event`.
2. Incoming events append to Evolution event log; metrics polled every 10s.

## 6. File Layout (Target)

```
src/
  pages/           # Landing.tsx, Dashboard.tsx
  components/      # AgentsPanel, TasksPanel, ToolsPanel, MemoryPanel, EvolutionPanel, StatusLight
  api/             # client.ts (fetch wrapper), tasks.ts, tools.ts, agents.ts, memories.ts, evolution.ts
  ws/              # socket.ts, useGenesisSocket.ts, subscriptions.ts
  types/           # ws.ts, api.ts (API DTOs mirroring the gateway's Pydantic schemas)
  lib/             # format.ts (durations, percentages), time.ts
```

## 7. Developer Conventions

- DTO types in `types/api.ts` mirror Pydantic schema field names 1:1 (camelCase converted at the client wrapper level if the gateway uses snake_case).
- No component fetches directly — always through hooks that wrap the REST/WS clients.
- All panels degrade gracefully: loading skeletons, error states with retry, and empty states.
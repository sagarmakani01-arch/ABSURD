# ABSURD — Architecture Audit (Phase 0)

Date: 2026-08-20
Status: pre-implementation baseline

## 1. Current Stack

| Layer | Status |
|---|---|
| Repository | Empty scaffold. No framework, no package manager, no runtime config. |
| Existing files | `docs/` only — 7 architecture documents written during requirements analysis (ARCHITECTURE.md, api-gateway.md, agent-engine.md, tool-system.md, memory-system.md, evolution-loop.md, frontend.md). |
| Frontend | None. |
| Backend | None. |
| Database | None. |
| Execution sandbox | None. |
| CI / tooling (lint, format, test) | None. |
| SCM | GitHub remote `sagarmakani01-arch/ABSURD` (main branch, single README, "Initial commit"). |

## 2. Current Structure

```
absurd/
  docs/
    ARCHITECTURE.md, api-gateway.md, agent-engine.md,
    tool-system.md, memory-system.md, evolution-loop.md, frontend.md
```

No source code exists. Nothing to migrate, nothing to delete.

## 3. Existing Entry Points

None runtime. The remote README is the only user-facing artifact.

## 4. Host Environment (verified)

| Tool | Version | Notes |
|---|---|---|
| Node.js | v24.16.0 | Supports Vite 6/7, modern tooling. |
| npm | 11.13.0 | OK. |
| Python | 3.14.4 | New ABI. Pin pydantic-core/SQLAlchemy to versions with cp314 wheels; test import early. |
| git | 2.54.0 | OK. |
| gh (GitHub CLI) | 2.96.0 | Authenticated as `sagarmakani01-arch`; token has `repo` scope — push-capable. |
| Docker | not verified | Sandbox executor will require Docker; document as a runtime prerequisite, never execute generated code on the host. |

## 5. Dependency Issues

- No dependencies exist yet.
- **Planned risks to watch:**
  - Python 3.14 wheel availability for `pydantic-core` (FastAPI/Pydantic v2) — resolve early in Phase 1 install.
  - `SQLModel` lagging behind 3.14; primary target `SQLAlchemy 2.x`, SQLModel only if compatible.
  - Frontend GPU/viz deps (`three`, `@react-three/fiber`) are large; keep them lazy-loaded behind the hero route.

## 6. Recommended Target Architecture

- **Monorepo layout** (single package per concern):
  - `frontend/` — Vite + React 18 + TypeScript + Tailwind CSS v4 + Framer Motion + GSAP + Three.js/R3F + Lucide.
  - `backend/` — FastAPI + Pydantic v2 + WebSockets; SQLite via SQLAlchemy 2.x; pytest; Ruff + Black.
  - `docs/` — architecture, security, tool lifecycle, evaluation, performance, roadmap.
  - `.opencode/skills/` — UI/UX Pro Max skill (installed from `nextlevelbuilder/ui-ux-pro-max-skill`).
- **Backend module skeleton** (from requirements):
  - `app/api/routes/`, `app/agent/` (planner, reasoner, capability_detector, task_manager),
    `app/tools/` (registry, generator, validator, versioning, composer),
    `app/sandbox/` (manager, executor, policy) — Docker-isolated, never host-executed,
    `app/memory/` (tool_memory, experience_memory, capability_memory),
    `app/evaluation/`, `app/models/`, `app/services/` (llm, events), `app/security/`.
- **Event system**: internal event bus; every state transition emits typed events (TASK_CREATED → CAPABILITY_GAP_DETECTED → TOOL_REGISTERED → TASK_COMPLETED …). WS bridge streams them to the UI.
- **Tool model + lifecycle**: formal Tool object with versioning (v1→v2→… via parent_version); lifecycle DRAFT → GENERATED → VALIDATING → TESTING → BENCHMARKING → VERIFIED → REGISTERED, with failure states TEST_FAILED / SECURITY_REJECTED / BENCHMARK_FAILED / GENERATION_FAILED.

## 7. Migration Risks

| Risk | Severity | Mitigation |
|---|---|---|
| Python 3.14 ecosystem lag | Medium | Verify FastAPI/pydantic/SQLAlchemy install first in Phase 1; pin working versions. |
| Docker unavailable on host | High (execution) | Sandbox module must fail closed: no Docker → execution blocked, not degraded to host execution. |
| OneDrive-local repo path | Low | Live sync may slow builds; keep `node_modules`, `.venv`, build output git-ignored. |
| Remote repo merge conflicts | Low | Remote has a single README; pull/rebase before first push. |
| Monitoring of "no fake AI" rule | Medium | All AI-dependent paths (LLM service) ship as explicit `NotImplemented`/stub abstractions until real backends land; deterministic rule-based paths (registry matching, validation) implemented for real. |

## 8. Phase Gate

Phase 0 complete. Next: install UI/UX Pro Max skill + scaffold Phase 1 target stack (frontend deps, backend venv, initial FastAPI app, SQLite init).
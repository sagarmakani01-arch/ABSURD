# ABSURD Evolution Loop

> **Status note (Phase 14):** failure analysis also counts **unfillable
> gaps** — capabilities whose generation has been refused
> `ABSURD_UNFILLABLE_GAP_THRESHOLD` times are marked unfillable in the
> knowledge graph, and later tasks over the same gap fail `NO_CAPABILITY`
> with `ATTEMPTS` instead of seeding futile DRAFT candidates. Tool
> executions now also feed **composition** results (chained tools count as
> multi-step executions). Metrics include `tools_disabled` and
> `unfillable_gaps`.

The Evolution Loop is what makes ABSURD self-improving. Every tool execution outcome is either **registered** (success) or **analyzed** (failure); both paths write back into memory, which improves the next task's plan, capability coverage, and tool quality.

```
              TOOL EXECUTION
                    │
          ┌─────────┴─────────┐
          ▼                   ▼
        SUCCESS             FAILURE
          │                   │
          ▼                   ▼
       REGISTER             ANALYZE
          │                   │
          └────────┬──────────┘
                   ▼
             EVOLUTION LOOP
        (memory writes + events +
         re-plan triggers)
```

## 1. The Success Path — REGISTER

Triggered by `status == success` (or `partial` with usable results).

1. Validate the tool record against Tool Memory (idempotency: skip if already registered).
2. Promote candidate → registered tool:
   - `provenance = "generated"` from the originating `source_task_id`
   - `status = "active"`, initial `confidence` from the generator's validation score
3. Write Knowledge Graph edges: `Tool ─enables→ Capability`, `Capability ─covers→ Goal` (from the task that produced it).
4. Update Tool Memory aggregates: `usage_count += 1`, `success_rate` recomputed.
5. Persist Experience Memory record.
6. Emit `tool.registered` event (WS) — the dashboard turns green; the capability is now available to all future planners.

## 2. The Failure Path — ANALYZE

Triggered by `status in {failure, invalid_output, violation, timeout}`.

1. **Classify** the failure (table in `tool-system.md` §5).
2. **Root-cause analysis**:
   - deterministic: schema mismatch vs sandbox violation vs timeout (structured fields, no NLP needed);
   - LLM-assisted (optional): open-ended reasoning from sanitized traces for `runtime_error` cases.
3. **Write lessons** to Experience Memory (`lessons[]` on the execution record).
4. **Knowledge Graph:**
   - `FailurePattern ─blocks→ Goal` (if the step remains unfulfillable);
   - `Tool ─satisfies→ FailurePattern` (if a subsequent successful attempt fixed it).
5. **Trigger re-plan** (if retries remain): emit an internal event consumed by the Reasoner → Planner revision. The revised plan is tried up to `max_retries`.
6. Emit `evolution.event` with `event_type: failure.analyzed`.

## 3. Loop Convergence Rules

- A gap that fails generation twice in a row is marked `unfillable_gap` and becomes a persistent KG node — later runs check this node before generating again, avoiding repeated futile generation.
- A tool that fails execution 3× consecutively is **quarantined** (removed from active registry, flagged in Tool Memory); it must be regenerated or edited to re-enter.
- A tool's `confidence` decays while unused (halving every 30 days) so stale capabilities don't outrank fresh ones; the dashboard surfaces "low-confidence" tools.

## 4. Event Types (append-only log, `GET /evolution/events`)

| `event_type` | When | Payload highlights |
|---|---|---|
| `tool.generated` | a candidate tool was produced | gap_spec, generator strategy |
| `tool.registered` | success path completed | tool_id, confidence |
| `failure.analyzed` | failure path completed | tool_id, failure kind, lessons |
| `capability.gap` | gap declared unfillable | step, gap_spec, attempts |
| `tool.quarantined` | 3 consecutive failures | tool_id, failure history |
| `plan.revised` | re-plan triggered after analysis | task_id, revision reason |

## 5. What Improves Between Iterations

| Loop output | Improves |
|---|---|
| New registered tool | Capability coverage (Capability Detector finds fewer gaps) |
| Failure lessons | Planner seeds better plans (`memory-guided`), Reasoner avoids known pitfalls |
| KG edges | Composition checks become possible ("these two tools together cover goal X") |
| Quarantine decisions | Decreased flaky-tool usage across future tasks |

## 6. Loop Metrics (exposed to the dashboard)

- tools generated / registered / quarantined per period
- mean generation-to-registration time
- gap-close rate: fraction of detected gaps eventually covered by a registered tool
- failure rate by kind (what the `failure.analyzed` events aggregate)
- loop iterations per task
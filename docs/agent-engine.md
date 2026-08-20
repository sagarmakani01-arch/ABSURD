# GENESIS Agent Engine

The Agent Engine is the cognitive core. It turns a high-level goal into a sequence of executable steps, decides whether existing tools can handle them, and reasons over outcomes. It is composed of three components: **Planner**, **Capability Detector**, and **Reasoner**.

```
Task (goal) ──► Planner ──► steps ──► Capability Detector ──► execution plan
                                      │                          │
                              (gap found? ──► Tool Generator)    │
                                                                ▼
                                        Reasoner ◄── tool results/outcomes
```

## 1. Planner

- **Input:** `goal: str`, `context: dict`, optional prior memory hints.
- **Output:** ordered `steps: Step[]`, each `{id, description, expected_inputs, expected_outputs, confidence}`.
- Strategies (pluggable, selected per agent config):
  - `hierarchical` — decompose the goal into sub-goals, then leaf actions.
  - `reactive` — generate steps sequentially, re-planning after each outcome (used with streaming tasks).
  - `memory-guided` — seed the plan from Experience Memory: similar past tasks' step sequences are replayed with edits.
- **Contract:** the Planner never executes anything directly; it produces a plan that the Capability Detector annotates.

## 2. Capability Detector

- **Input:** planned `steps`.
- **Output:** `CapabilityPlan[]`, where each entry is one of:
  - `covered` — a registered tool (from the Tool Registry / Tool Memory) exists whose schema matches the step's `expected_inputs`/`expected_outputs`.
  - `partial` — existing tools can cover part of the step; the remainder needs composition or generation.
  - `gap` — no registered tool matches; the step is marked for **Tool Generation**.
- Matching logic (deterministic, cached):
  1. Exact signature match (parameter names, types, return type).
  2. Semantic match via embedding similarity against tool descriptions (threshold-configurable).
  3. Composition check: can a chain of registered tools produce the required output?
- **Output detail per step:** `{step_id, coverage, matched_tool_ids?, gap_spec?}` where `gap_spec` is the schema the Tool Generator must satisfy: `{name_hint, description, input_schema, output_schema, security_constraints}`.

## 3. Reasoner

- **Input:** plan + tool execution outcomes (success results, failure errors, partial results).
- **Output:** one or more of:
  - `plan_revision` — instructions for the Planner (retry with different approach, reorder steps, split a failing step).
  - `tool_feedback` — structured outcome passed to the Evolution Loop (`success`/`failure` event with metadata).
  - `task_result` — final answer assembled from tool results.
  - `confidence` — per-step and overall task confidence.
- Behaviors:
  - Deterministic aggregation of structured results (schema-driven).
  - LLM-assisted reasoning (optional backend, configurable) for open-ended synthesis and failure analysis.
  - Always emits machine-readable outcome records so the Memory System and Evolution Loop can consume them without free-text parsing.

## 4. Interfaces (internal)

```
Planner.perform(goal, context, memory_hints) -> Plan
CapabilityDetector.evaluate(plan) -> CapabilityPlan[]
Reasoner.synthesize(capability_plan, outcomes) -> ReasonerOutput
```

All three are invoked by the Agent Engine orchestrator (`AgentEngine.run(task)`), which owns the execution loop:

```
plan = planner.perform(goal, ctx)
capabilities = detector.evaluate(plan)
for step in capabilities:
    if gap: result = tool_system.generate_and_execute(step.gap_spec)
    else:   result = tool_system.execute(matched_tools, step)
    outcomes.append(result)
    revision = reasoner.synthesize(plan, outcomes)
    if revision.plan_revision: plan = planner.perform(goal, ctx, revision)
output = reasoner.finalize(outcomes)
```

## 5. Memory Hooks

- Reads: past task plans (Experience Memory), tool existence (Tool Memory).
- Writes: `task` outcomes + reasoned conclusions (Experience Memory), new relationships in the Knowledge Graph (e.g., `tool A enables goal G`).

## 6. Failure & Recovery

- Step failure does not abort the task immediately: the Reasoner gets up to `max_retries` (default 2) with plan revisions.
- If a gap is unfillable after generation attempts, the task fails gracefully with a structured `error` that names the missing capability — this is recorded as an evolution `capability.gap` event for future runs.
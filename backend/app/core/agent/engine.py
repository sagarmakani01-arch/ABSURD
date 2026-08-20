"""Agent engine — owns the deterministic execution loop for a task.

Phase 6 loop: analyze -> plan -> detect capability -> verdict.
Phase 7: registry lifecycle; Phase 8: tool generation for gaps.
Phase 13b: covered plans are actually executed — every covered step runs its
matched REGISTERED tool in the sandbox with the task's input hints, and the
task's verdict reflects the real outcomes (EXECUTED on full success,
TOOL_EXECUTION_FAILED / TOOL_NOT_AVAILABLE on the first failure). Tools that
fail 3 executions in a row are quarantined by the evolution loop.
Phase 14: retries — an execution failure re-plans and retries up to the
agent's `max_retries` budget (PLAN_REVISED events between attempts), and a
cancellation request made through a separate request thread is honoured
between steps. Composition chains (two tools whose schemas link) execute as
A then B with A's output fed into B.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

import app.config as config
from app.core.agent.detector import CapabilityDetector, CapabilityPlan, Coverage
from app.core.agent.planner import Plan, Planner
from app.core.agent.reasoner import Reasoner
from app.core.tools.model import ToolStatus
from app.core.tools.registry import tool_registry
from app.events import EventType, bus
from app.models import AgentRecord, TaskRecord, ToolRecord
from app.services.evolution import evolution_service
from app.services.generator import tool_generator
from app.services.memory import knowledge_graph
from app.services.sandbox import sandbox
from app.services.semantic import semantic_service


class AgentEngine:
    def __init__(self) -> None:
        self.planner = Planner()
        self.detector = CapabilityDetector(semantic_tier=semantic_service)
        self.reasoner = Reasoner()

    def run(self, session: Session, task: TaskRecord) -> TaskRecord:
        """Execute one task through the loop. Mutates and persists `task`."""
        bus.publish(EventType.TASK_ANALYZED, {"task_id": task.id, "goal": task.goal[:200]})
        task.status = "ANALYZED"
        max_retries = self._max_retries_for(session, task)

        attempts = 0
        while True:
            if self._is_cancelled(session, task):
                session.refresh(task)
                return task

            plan = self.planner.perform(task.goal, task.context)
            bus.publish(
                EventType.CAPABILITY_CHECK_STARTED,
                {"task_id": task.id, "steps": len(plan.steps)},
            )

            capabilities = self.detector.evaluate(plan, tool_registry.registered_tools(session))
            self._seed_gaps(session, task, capabilities)

            verdict = self.reasoner.synthesize(plan, capabilities, tool_generator.generate_available())
            if verdict.error:
                task.status = "FAILED"
                task.result = verdict.task_result
                task.error = verdict.error
                task.error["attempts"] = attempts + 1
                bus.publish(
                    EventType.TASK_FAILED,
                    {
                        "task_id": task.id,
                        "kind": verdict.error["kind"],
                        "missing": verdict.error["missing"],
                        "generation_available": verdict.error.get("generation_available", False),
                        "attempts": attempts + 1,
                    },
                )
                break

            executed = self._execute_steps(session, task, plan, capabilities)
            if executed:
                break
            if self._is_cancelled(session, task):
                session.refresh(task)
                return task
            if attempts >= max_retries:
                break
            attempts += 1
            bus.publish(
                EventType.PLAN_REVISED,
                {
                    "task_id": task.id,
                    "attempt": attempts,
                    "reason": "execution failed; registry state may have changed",
                    "execution_status": (task.error or {}).get("execution_status"),
                },
            )
            task.status = "ANALYZED"
            task.error = None
            task.result = None
            session.add(task)
            session.commit()

        if task.status == "FAILED" and isinstance(task.error, dict) and "attempts" not in task.error:
            task.error["attempts"] = attempts + 1
        session.add(task)
        session.commit()
        session.refresh(task)
        return task

    def _seed_gaps(
        self, session: Session, task: TaskRecord, capabilities: CapabilityPlan
    ) -> None:
        """Publish capability signals and seed DRAFT candidates for gaps.

        A capability whose candidates were rejected `UNFILLABLE_GAP_THRESHOLD`
        times is declared unfillable: no new candidate is seeded and a
        `capability.gap_unfillable` event is emitted (later runs short-circuit
        the same way instead of generating repeatedly).
        """
        generation_available = tool_generator.generate_available()
        for entry in capabilities.entries:
            if entry.coverage.value == "gap" and entry.gap_spec:
                bus.publish(
                    EventType.CAPABILITY_MISSING,
                    {"task_id": task.id, "step_id": entry.step_id, "capability": entry.gap_spec.name_hint},
                )
                bus.publish(
                    EventType.CAPABILITY_REQUIRED,
                    {
                        "task_id": task.id,
                        "step_id": entry.step_id,
                        "gap_spec": entry.gap_spec.model_dump(),
                        "generation_available": generation_available,
                    },
                )
                if generation_available:
                    self._seed_one(session, task, entry.gap_spec.name_hint, entry.gap_spec.model_dump())
            elif entry.coverage.value == "partial":
                bus.publish(
                    EventType.CAPABILITY_REQUIRED,
                    {
                        "task_id": task.id,
                        "step_id": entry.step_id,
                        "gap_spec": entry.gap_spec.model_dump() if entry.gap_spec else None,
                        "matched_tool_ids": entry.matched_tool_ids,
                        "generation_available": generation_available,
                    },
                )
                if generation_available and entry.gap_spec:
                    self._seed_one(session, task, entry.gap_spec.name_hint, entry.gap_spec.model_dump())
            elif entry.coverage.value == "covered":
                bus.publish(
                    EventType.CAPABILITY_FOUND,
                    {
                        "task_id": task.id,
                        "step_id": entry.step_id,
                        "matched_tool_ids": entry.matched_tool_ids,
                    },
                )

        if capabilities.has_gap:
            bus.publish(
                EventType.CAPABILITY_GAP_DETECTED,
                {
                    "task_id": task.id,
                    "gaps": [g.name_hint for g in capabilities.gaps if g],
                },
            )

    def _seed_one(self, session: Session, task: TaskRecord, capability: str, gap_spec: dict[str, object]) -> None:
        from app.core.agent.detector import GapSpec

        fillable, rejected = tool_generator.gap_fillable(session, capability)
        if not fillable:
            bus.publish(
                EventType.CAPABILITY_GAP_UNFILLABLE,
                {
                    "task_id": task.id,
                    "capability": capability,
                    "rejected_count": rejected,
                },
            )
            knowledge_graph.record_unfillable(
                session, capability=capability, task_id=task.id, rejected_count=rejected
            )
            return
        tool_generator.generate(session, GapSpec(**gap_spec), source_task_id=task.id)

    def _execute_steps(
        self, session: Session, task: TaskRecord, plan: Plan, capabilities: CapabilityPlan
    ) -> bool:
        """Run every covered step through the sandbox; False = task failed."""
        step_inputs = self._resolve_step_inputs(plan, task.context)
        outputs: list[dict[str, object]] = []
        for index, (step, entry) in enumerate(zip(plan.steps, capabilities.entries)):
            if self._is_cancelled(session, task):
                session.refresh(task)
                return False

            running = list(entry.matched_tool_ids)
            if not running:
                self._fail(
                    session,
                    task,
                    "TOOL_NOT_AVAILABLE",
                    {"tool_id": "", "step_id": step.id, "detail": "no tool matched the step"},
                )
                return False

            tool = session.get(ToolRecord, running[0])
            if tool is None or tool.status != ToolStatus.REGISTERED.value:
                self._fail(
                    session,
                    task,
                    "TOOL_NOT_AVAILABLE",
                    {
                        "tool_id": running[0],
                        "step_id": step.id,
                        "detail": f"matched tool {running[0]} is not registered",
                    },
                )
                return False

            inputs = step_inputs[index]
            for index_in_chain, tool_id in enumerate(running):
                if self._is_cancelled(session, task):
                    session.refresh(task)
                    return False
                tool = session.get(ToolRecord, tool_id)
                if tool is None or tool.status != ToolStatus.REGISTERED.value:
                    self._fail(
                        session,
                        task,
                        "TOOL_NOT_AVAILABLE",
                        {
                            "tool_id": tool_id,
                            "step_id": step.id,
                            "detail": f"matched tool {tool_id} is not registered",
                        },
                    )
                    return False
                record = sandbox.execute(session, tool, inputs, task_id=task.id)
                if record.status != "COMPLETED":
                    code = record.error.get("code") if record.error else "execution_failed"
                    self._fail(
                        session,
                        task,
                        "TOOL_EXECUTION_FAILED",
                        {
                            "tool_id": tool.id,
                            "tool_version": tool.version,
                            "step_id": step.id,
                            "execution_status": record.status,
                            "code": code,
                            "detail": (record.error or {}).get("message", "execution failed"),
                            "chain": running,
                            "chain_index": index_in_chain,
                        },
                    )
                    return False
                feed = record.output or {}
                inputs = feed
                outputs.append({"step_id": step.id, "tool_id": tool.id, "output": feed})

        evolution_service.quarantine(session)
        task.status = "COMPLETED"
        task.error = None
        task.result = {
            "kind": "EXECUTED",
            "detail": "All steps executed in the sandbox; outputs recorded.",
            "steps": len(plan.steps),
            "outputs": outputs,
        }
        bus.publish(
            EventType.TASK_COMPLETED,
            {"task_id": task.id, "confidence": 1.0, "executed": True, "outputs": outputs},
        )
        return True

    def _fail(self, session: Session, task: TaskRecord, kind: str, extra: dict[str, object]) -> None:
        """Honest structured failure on the first thing that went wrong."""
        evolution_service.quarantine(session)
        task.status = "FAILED"
        task.result = None
        task.error = {"kind": kind, **extra}
        bus.publish(
            EventType.TASK_FAILED,
            {"task_id": task.id, "kind": kind, "missing": [], **extra},
        )

    def _max_retries_for(self, session: Session, task: TaskRecord) -> int:
        if task.agent_id:
            agent = session.get(AgentRecord, task.agent_id)
            if agent is not None:
                return max(0, int(agent.max_retries))
        return config.REPLAN_MAX_RETRIES

    @staticmethod
    def _is_cancelled(session: Session, task: TaskRecord) -> bool:
        """Fresh status read — honours a cancel request from another thread.

        Reads the row directly so pending (uncommitted) task mutations in
        this session's identity map are never clobbered by a reload.
        """
        from sqlalchemy import select as _select

        fresh = session.execute(
            _select(TaskRecord.status).where(TaskRecord.id == task.id)
        ).scalar_one_or_none()
        return fresh == "CANCELLED"

    @staticmethod
    def _resolve_step_inputs(plan: Plan, context: dict[str, object] | None) -> list[dict[str, object]]:
        """Per-step concrete input values from optional `context["inputs"]`.

        The list is aligned with the plan steps; unknown keys are passed
        through as-is and the sandbox validates against the tool's declared
        input schema. With no hints a step executes with `{}` — tools that
        require inputs then fail input_validation rather than fabricating data.
        """
        resolved: list[dict[str, object]] = [{} for _ in plan.steps]
        hints = context.get("inputs") if isinstance(context, dict) else None
        if isinstance(hints, list):
            for index, hint in enumerate(hints[: len(plan.steps)]):
                if isinstance(hint, dict):
                    resolved[index] = {str(k): v for k, v in hint.items()}
        return resolved


agent_engine = AgentEngine()
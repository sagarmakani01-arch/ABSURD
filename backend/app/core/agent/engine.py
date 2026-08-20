"""Agent engine — owns the deterministic execution loop for a task.

Phase 6 loop: analyze -> plan -> detect capability -> verdict.
Phase 7: registry lifecycle; Phase 8: tool generation for gaps.
Phase 13b: covered plans are actually executed — every covered step runs its
matched REGISTERED tool in the sandbox with the task's input hints, and the
task's verdict reflects the real outcomes (EXECUTED on full success,
TOOL_EXECUTION_FAILED / TOOL_NOT_AVAILABLE on the first failure). Tools that
fail 3 executions in a row are quarantined by the evolution loop.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.agent.detector import CapabilityDetector, CapabilityPlan, Coverage
from app.core.agent.planner import Plan, Planner
from app.core.agent.reasoner import Reasoner
from app.core.tools.model import ToolStatus
from app.core.tools.registry import tool_registry
from app.events import EventType, bus
from app.models import TaskRecord, ToolRecord
from app.services.evolution import evolution_service
from app.services.generator import tool_generator
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

        plan = self.planner.perform(task.goal, task.context)
        bus.publish(
            EventType.CAPABILITY_CHECK_STARTED,
            {"task_id": task.id, "steps": len(plan.steps)},
        )

        capabilities = self.detector.evaluate(plan, tool_registry.registered_tools(session))
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
                # Self-extension: seed a DRAFT candidate for the gap (idempotent).
                if generation_available:
                    tool_generator.generate(session, entry.gap_spec, source_task_id=task.id)
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
                    tool_generator.generate(session, entry.gap_spec, source_task_id=task.id)
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

        verdict = self.reasoner.synthesize(plan, capabilities, generation_available)
        if verdict.error:
            task.status = "FAILED"
            task.result = verdict.task_result
            task.error = verdict.error
            bus.publish(
                EventType.TASK_FAILED,
                {
                    "task_id": task.id,
                    "kind": verdict.error["kind"],
                    "missing": verdict.error["missing"],
                    "generation_available": verdict.error.get("generation_available", False),
                },
            )
        else:
            self._execute_steps(session, task, plan, capabilities)

        session.add(task)
        session.commit()
        session.refresh(task)
        return task

    def _execute_steps(
        self, session: Session, task: TaskRecord, plan: Plan, capabilities: CapabilityPlan
    ) -> None:
        """Run every covered step through the sandbox; verdict reflects reality."""
        step_inputs = self._resolve_step_inputs(plan, task.context)
        outputs: list[dict[str, object]] = []
        for index, (step, entry) in enumerate(zip(plan.steps, capabilities.entries)):
            tool_id = entry.matched_tool_ids[0] if entry.matched_tool_ids else None
            tool = session.get(ToolRecord, tool_id) if tool_id else None
            if tool is None or tool.status != ToolStatus.REGISTERED.value:
                self._fail(
                    session,
                    task,
                    "TOOL_NOT_AVAILABLE",
                    {
                        "tool_id": tool_id or "",
                        "step_id": step.id,
                        "detail": f"matched tool {tool_id} is not registered",
                    },
                )
                return
            record = sandbox.execute(session, tool, step_inputs[index], task_id=task.id)
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
                    },
                )
                return
            outputs.append({"step_id": step.id, "tool_id": tool.id, "output": record.output})

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
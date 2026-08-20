"""Agent engine — owns the deterministic execution loop for a task.

Phase 6 loop: analyze → plan → detect capability → verdict.
Phase 7 inserts execution; Phase 8 inserts tool generation for gaps.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.agent.detector import CapabilityDetector
from app.core.agent.planner import Planner
from app.core.agent.reasoner import Reasoner
from app.core.tools.registry import tool_registry
from app.events import EventType, bus
from app.models import TaskRecord


class AgentEngine:
    def __init__(self) -> None:
        self.planner = Planner()
        self.detector = CapabilityDetector()
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
        generation_available = False  # requires LLM backend + sandbox (later phases)
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
        task.status = "FAILED" if verdict.error else "COMPLETED"
        task.result = verdict.task_result
        task.error = verdict.error

        if verdict.error:
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
            bus.publish(EventType.TASK_COMPLETED, {"task_id": task.id, "confidence": verdict.confidence})

        session.add(task)
        session.commit()
        session.refresh(task)
        return task


agent_engine = AgentEngine()
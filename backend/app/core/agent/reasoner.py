"""Deterministic Reasoner (v0).

Consumes the capability plan and produces a machine-readable verdict: either
a structured failure naming the missing capabilities, or a completion record.
LLM-assisted synthesis is optional future work (docs/agent-engine.md).
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.core.agent.detector import CapabilityPlan, Coverage, GapSpec
from app.core.agent.planner import Plan


class ReasonerOutput(BaseModel):
    confidence: float
    task_result: dict[str, object] | None = None
    error: dict[str, object] | None = None
    step_feedback: list[dict[str, object]] = Field(default_factory=list)


class Reasoner:
    def synthesize(
        self,
        plan: Plan,
        capability_plan: CapabilityPlan,
        generation_available: bool = False,
    ) -> ReasonerOutput:
        feedback: list[dict[str, object]] = []
        for entry in capability_plan.entries:
            feedback.append(
                {
                    "step_id": entry.step_id,
                    "coverage": entry.coverage.value,
                    "matched_tool_ids": entry.matched_tool_ids,
                    "confidence": entry.confidence,
                }
            )

        if capability_plan.has_gap:
            missing = [gap.name_hint for gap in capability_plan.gaps if gap]
            return ReasonerOutput(
                confidence=0.0,
                error={
                    "kind": "NO_CAPABILITY",
                    "missing": missing,
                    "generation_available": generation_available,
                    "detail": "No registered tool covers the required steps."
                    if not generation_available
                    else "Missing capabilities queued for tool generation.",
                },
                step_feedback=feedback,
            )

        if capability_plan.has_partial:
            missing = [gap.name_hint for gap in capability_plan.partials if gap]
            return ReasonerOutput(
                confidence=0.7,
                error={
                    "kind": "PARTIAL_CAPABILITY",
                    "missing": missing,
                    "generation_available": generation_available,
                    "detail": "Registered tools fit part of the steps; composition or "
                    "generation is required to finish.",
                },
                step_feedback=feedback,
            )

        return ReasonerOutput(
            confidence=1.0,
            task_result={
                "kind": "PLANNED",
                "detail": "All steps are covered by registered tools; "
                "tool execution is not implemented yet (sandbox phase).",
                "steps": len(plan.steps),
            },
            step_feedback=feedback,
        )
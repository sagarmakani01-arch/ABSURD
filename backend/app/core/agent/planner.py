"""Deterministic Planner (v0).

Turns a goal into an ordered list of steps. No LLM is used: v0 splits the goal
on explicit coordination boundaries (` and `, ` then `, `; `). Richer
strategies (hierarchical, reactive, memory-guided) are documented in
docs/agent-engine.md and land in later phases.
"""

from __future__ import annotations

import re
from uuid import uuid4

from pydantic import BaseModel, Field

SEPARATOR = re.compile(r"\s+(?:and|then)\s+|\s*;\s*|\s*\n\s*")


class Step(BaseModel):
    """A single unit of work produced by the Planner."""

    id: str = Field(default_factory=lambda: uuid4().hex)
    description: str
    expected_inputs: dict[str, str] = Field(default_factory=dict)
    expected_outputs: dict[str, str] = Field(default_factory=dict)
    confidence: float = 0.5


class Plan(BaseModel):
    """An ordered, annotated decomposition of a goal."""

    goal: str
    strategy: str
    steps: list[Step] = Field(default_factory=list)


class Planner:
    """Deterministic goal decomposition."""

    def perform(self, goal: str, context: dict[str, object] | None = None) -> Plan:
        """Decompose `goal` into steps. Never executes anything.

        Optional `context["expected_io"]` is a list of `{"inputs": {...},
        "outputs": {...}}` hints aligned positionally with the steps; when
        present they feed schema-based capability detection.
        """
        context = context or {}
        segments = [s.strip() for s in SEPARATOR.split(goal) if s.strip()]
        if not segments:
            segments = [goal]
        steps = [
            Step(description=segment, confidence=0.5 if len(segments) > 1 else 1.0)
            for segment in segments
        ]
        io_hints = context.get("expected_io")
        if isinstance(io_hints, list):
            for index, hint in enumerate(io_hints[: len(steps)]):
                if not isinstance(hint, dict):
                    continue
                inputs = hint.get("inputs")
                outputs = hint.get("outputs")
                if isinstance(inputs, dict):
                    steps[index].expected_inputs = {str(k): str(v) for k, v in inputs.items()}
                if isinstance(outputs, dict):
                    steps[index].expected_outputs = {str(k): str(v) for k, v in outputs.items()}
        strategy = "split" if len(steps) > 1 else "flat"
        return Plan(goal=goal, strategy=strategy, steps=steps)
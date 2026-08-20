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
        """Decompose `goal` into steps. Never executes anything."""
        segments = [s.strip() for s in SEPARATOR.split(goal) if s.strip()]
        if not segments:
            segments = [goal]
        steps = [
            Step(description=segment, confidence=0.5 if len(segments) > 1 else 1.0)
            for segment in segments
        ]
        strategy = "split" if len(steps) > 1 else "flat"
        return Plan(goal=goal, strategy=strategy, steps=steps)
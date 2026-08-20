"""Deterministic Capability Detector (v0).

Annotates each planned step with one of `covered` / `partial` / `gap`.
Matching in v0 is lexical: a step is covered when a REGISTERED tool's name
appears in the step description. Schema/semantic matching lands with the Tool
Registry (Phase 7); the interface here is final.
"""

from __future__ import annotations

import re
from enum import StrEnum

from pydantic import BaseModel, Field

from app.core.agent.planner import Plan


class Coverage(StrEnum):
    COVERED = "covered"
    PARTIAL = "partial"
    GAP = "gap"


class GapSpec(BaseModel):
    """What a generated tool must satisfy to cover a gap."""

    name_hint: str
    description: str
    input_schema: dict[str, str] = Field(default_factory=dict)
    output_schema: dict[str, str] = Field(default_factory=dict)
    security_constraints: list[str] = Field(default_factory=list)


class CapabilityEntry(BaseModel):
    step_id: str
    coverage: Coverage
    matched_tool_ids: list[str] = Field(default_factory=list)
    gap_spec: GapSpec | None = None


class CapabilityPlan(BaseModel):
    entries: list[CapabilityEntry] = Field(default_factory=list)

    @property
    def has_gap(self) -> bool:
        return any(e.coverage is Coverage.GAP for e in self.entries)

    @property
    def gaps(self) -> list[GapSpec]:
        return [e.gap_spec for e in self.entries if e.coverage is Coverage.GAP and e.gap_spec]


class RegistryTool:
    """Duck-typed shape of a registered tool (satisfied by ToolRecord)."""

    def __init__(self, id: str, name: str, capabilities: list[str]) -> None:
        self.id = id
        self.name = name
        self.capabilities = capabilities


class CapabilityDetector:
    """Maps steps to registry coverage. Deterministic; no LLM."""

    def evaluate(self, plan: Plan, tools: list[RegistryTool]) -> CapabilityPlan:
        entries: list[CapabilityEntry] = []
        for step in plan.steps:
            matched = [t.id for t in tools if self._covers(t, step.description)]
            if matched:
                entries.append(
                    CapabilityEntry(step_id=step.id, coverage=Coverage.COVERED, matched_tool_ids=matched)
                )
            else:
                entries.append(
                    CapabilityEntry(
                        step_id=step.id,
                        coverage=Coverage.GAP,
                        gap_spec=self._gap_spec(step.description),
                    )
                )
        return CapabilityPlan(entries=entries)

    @staticmethod
    def _covers(tool: RegistryTool, description: str) -> bool:
        """v0 lexical matching: tool name appears in the step description."""
        return tool.name.lower() in description.lower()

    @staticmethod
    def _gap_spec(description: str) -> GapSpec:
        words = [w for w in re.split(r"\W+", description.lower()) if w][:3]
        return GapSpec(
            name_hint="_".join(words) or "undefined_tool",
            description=description,
        )
"""Deterministic Capability Detector (v1).

Annotates each planned step with one of `covered` / `partial` / `gap`.

Matching is two-tier and deterministic:
1. Schema matching — a module covers a step when a REGISTERED tool's
   input/output schema is type-compatible with the step's expected IO and a
   capability tag also matches. A step is PARTIAL when the tool matches inputs
   or outputs but not both (composition/generation still needed).
2. Lexical fallback — v0 behavior (tool name appears in the step
   description) remains the signal when no schema is declared.

Semantic (embedding) matching remains future work requiring an embedding
service — see docs/agent-engine.md.
"""

from __future__ import annotations

import re
from enum import StrEnum

from pydantic import BaseModel, Field

from app.core.agent.planner import Plan, Step

# Type compatibility: a declared value type is compatible with a schema type
# when equal, when the declared type is a subtype, or when one side is "any".
_NUMERIC = {"number", "int", "integer", "float"}
_TYPE_GROUPS: list[set[str]] = [
    _NUMERIC,
    {"str", "string", "text"},
    {"bool", "boolean"},
    {"list", "array"},
    {"dict", "object", "map"},
]


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
    confidence: float = 0.5


class CapabilityPlan(BaseModel):
    entries: list[CapabilityEntry] = Field(default_factory=list)

    @property
    def has_gap(self) -> bool:
        return any(e.coverage is Coverage.GAP for e in self.entries)

    @property
    def has_partial(self) -> bool:
        return any(e.coverage is Coverage.PARTIAL for e in self.entries)

    @property
    def gaps(self) -> list[GapSpec]:
        return [e.gap_spec for e in self.entries if e.coverage is Coverage.GAP and e.gap_spec is not None]

    @property
    def partials(self) -> list[GapSpec]:
        return [e.gap_spec for e in self.entries if e.coverage is Coverage.PARTIAL and e.gap_spec is not None]


class RegistryTool:
    """Duck-typed shape of a registered tool (satisfied by ToolRecord)."""

    def __init__(
        self,
        id: str,
        name: str,
        capabilities: list[str],
        input_schema: dict[str, str] | None = None,
        output_schema: dict[str, str] | None = None,
    ) -> None:
        self.id = id
        self.name = name
        self.capabilities = capabilities
        self.input_schema = input_schema or {}
        self.output_schema = output_schema or {}


class CapabilityDetector:
    """Maps steps to registry coverage. Deterministic; no LLM."""

    def evaluate(self, plan: Plan, tools: list[RegistryTool]) -> CapabilityPlan:
        entries: list[CapabilityEntry] = []
        for step in plan.steps:
            entries.append(self._evaluate_step(step, tools))
        return CapabilityPlan(entries=entries)

    def _evaluate_step(self, step: Step, tools: list[RegistryTool]) -> CapabilityEntry:
        scored: list[tuple[RegistryTool, int]] = []
        for tool in tools:
            score = self._match_score(tool, step)
            if score > 0:
                scored.append((tool, score))
        if not scored:
            return CapabilityEntry(
                step_id=step.id,
                coverage=Coverage.GAP,
                gap_spec=self._gap_spec(step),
                confidence=0.0,
            )

        best = max(scored, key=lambda pair: pair[1])
        tool, score = best
        if score >= 2:
            return CapabilityEntry(
                step_id=step.id,
                coverage=Coverage.COVERED,
                matched_tool_ids=[tool.id],
                confidence=1.0,
            )
        return CapabilityEntry(
            step_id=step.id,
            coverage=Coverage.PARTIAL,
            matched_tool_ids=[tool.id],
            gap_spec=self._gap_spec(step),
            confidence=0.7,
        )

    def _match_score(self, tool: RegistryTool, step: Step) -> int:
        """0 = no match; 1 = partial (lexical/IO half-match); 2 = full coverage.

        A full schema match (inputs and outputs compatible, capability tag
        matches) scores 2. Lexical name presence alone scores 1 (kept for v0
        compatibility), as does a single-direction IO match.
        """
        cap_match = any(self._tagged(tag, step.description) for tag in tool.capabilities)
        lexical = cap_match or self._name_match(tool, step.description)

        # No schema declared on the step: lexical match is full coverage (v0).
        if not step.expected_inputs and not step.expected_outputs:
            return 2 if lexical else 0

        input_ok = self._compatible(step.expected_inputs, tool.input_schema)
        output_ok = self._compatible(step.expected_outputs, tool.output_schema)

        # Schema compatibility is the authoritative signal in v1.
        if input_ok and output_ok:
            return 2
        if input_ok or output_ok:
            # One direction fits — the tool is relevant but cannot finish the
            # step alone (composition or generation needed).
            return 1
        return 0

    @staticmethod
    def _name_match(tool: RegistryTool, description: str) -> bool:
        return CapabilityDetector._tagged(tool.name, description)

    @staticmethod
    def _tagged(tag: str, description: str) -> bool:
        """Word-bag lexical match: 'parse_html_documents' hits 'parse html documents'.

        Slugified capability/name tokens (generated tools) are normalized to
        words on both sides so an underscored capability closes the gap that
        produced it.
        """
        words = re.split(r"\W+", tag.lower())
        if not words:
            return False
        target = re.split(r"\W+", description.lower())
        return all(w in target for w in words)

    @staticmethod
    def _compatible(expected: dict[str, str], schema: dict[str, str]) -> bool:
        if not expected:
            return False
        for name, declared in expected.items():
            actual = schema.get(name)
            if actual is None:
                return False
            if not CapabilityDetector._type_compatible(declared, actual):
                return False
        return True

    @staticmethod
    def _type_compatible(declared: str, actual: str) -> bool:
        declared = declared.strip().lower()
        actual = actual.strip().lower()
        if declared in {"any", "*"} or actual in {"any", "*"}:
            return True
        if declared == actual:
            return True
        return any(
            declared in group and actual in group for group in _TYPE_GROUPS
        )

    @staticmethod
    def _gap_spec(step: Step) -> GapSpec:
        words = [w for w in re.split(r"\W+", step.description.lower()) if w][:3]
        return GapSpec(
            name_hint="_".join(words) or "undefined_tool",
            description=step.description,
            input_schema=step.expected_inputs,
            output_schema=step.expected_outputs,
        )
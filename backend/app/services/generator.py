"""Tool generator — template (deterministic) and LLM-assisted strategies.

A `GapSpec` from the capability detector becomes a DRAFT candidate through
one of two strategies:

- template (deterministic, always available) — an explicit validate + echo
  scaffold that never claims real behavior;
- llm (Phase 13d, only when an LLM transport is configured) — the model
  writes the behavior; its output is contract-validated before it can enter
  the registry, and any model failure falls back to the template strategy
  with a visible `tool.generation_requested` error event.

Candidates enter the registry as DRAFT and must still pass the structural gate
(verify) and activation (register) before the capability detector can use them
to close a gap. Generation is idempotent per capability slug.
"""

from __future__ import annotations

import re
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

import app.config as config
from app.core.agent.detector import GapSpec
from app.core.tools.model import ToolStatus
from app.core.tools.registry import tool_registry
from app.events import EventType, bus
from app.models import ToolRecord
from app.services.llm import LLMError, llm_service

# Template-based generation is deterministic and needs no model service.
AVAILABLE_STRATEGIES = ["template"]


class GeneratorError(Exception):
    """Raised when a capability gap cannot or must not be generated."""

    def __init__(self, message: str, code: str = "generation_error") -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class ToolGenerator:
    def generate_available(self) -> bool:
        """True whenever at least one strategy is registered."""
        return bool(AVAILABLE_STRATEGIES)

    def strategies(self) -> list[str]:
        strategies = list(AVAILABLE_STRATEGIES)
        if llm_service.available:
            strategies.append("llm")
        return strategies

    def gap_fillable(self, session: Session, capability: str) -> tuple[bool, int]:
        """`(can_seed, rejected_count)` for a capability slug.

        A capability whose candidates were REJECTED
        `ABSURD_UNFILLABLE_GAP_THRESHOLD` times (default 2) is declared
        unfillable: generation is refused so the system stops producing
        futile candidates for it (loop convergence rule, evolution-loop.md).
        """
        rejected = 0
        for tool in session.scalars(select(ToolRecord)).all():
            if capability in (tool.capabilities or []) and tool.status == ToolStatus.REJECTED.value:
                rejected += 1
        return rejected < config.UNFILLABLE_GAP_THRESHOLD, rejected

    def generate(
        self,
        session: Session,
        gap_spec: GapSpec,
        *,
        source_task_id: str = "",
    ) -> tuple[ToolRecord, bool]:
        """Idempotently create (or return) a DRAFT candidate for a gap spec.

        Returns `(candidate, created)` — `created=False` when a candidate for
        the same capability slug already exists. Fails closed with 409 when
        the capability has been declared unfillable.
        """
        capability = sanitize_name(gap_spec.name_hint or gap_spec.description)
        if tool_registry.by_capability(session, capability):
            return tool_registry.by_capability(session, capability), False

        fillable, rejected = self.gap_fillable(session, capability)
        if not fillable:
            bus.publish(
                EventType.CAPABILITY_GAP_UNFILLABLE,
                {
                    "capability": capability,
                    "rejected_count": rejected,
                },
            )
            raise GeneratorError(
                f"capability {capability} is unfillable: {rejected} candidates rejected",
                "capability_unfillable",
            )

        if llm_service.available:
            try:
                return self._generate_with_llm(session, gap_spec, capability, source_task_id), True
            except LLMError as exc:
                bus.publish(
                    EventType.TOOL_GENERATION_REQUESTED,
                    {
                        "capability": capability,
                        "strategy": "llm",
                        "error": exc.code,
                        "detail": exc.message,
                        "fallback": True,
                    },
                )
        return self._generate_with_template(session, gap_spec, capability, source_task_id), True

    def _generate_with_template(
        self,
        session: Session,
        gap_spec: GapSpec,
        capability: str,
        source_task_id: str,
    ) -> ToolRecord:
        bus.publish(
            EventType.TOOL_GENERATION_STARTED,
            {"capability": capability, "strategy": "template"},
        )
        tool = ToolRecord(
            id=uuid4().hex,
            name=capability,
            description=gap_spec.description or f"Generated tool for {capability}",
            version="0.1.0",
            status="DRAFT",
            input_schema=dict(gap_spec.input_schema),
            output_schema=dict(gap_spec.output_schema),
            capabilities=[capability],
            tests=_generate_tests(capability, gap_spec),
            source_code=_template_source(capability, gap_spec),
            provenance={
                "strategy": "template",
                "generation_available": True,
                "source_task_id": source_task_id,
                "gap_spec": gap_spec.model_dump(),
            },
        )
        session.add(tool)
        session.commit()
        session.refresh(tool)
        bus.publish(
            EventType.TOOL_GENERATED,
            {"tool_id": tool.id, "capability": capability, "strategy": "template"},
        )
        return tool

    def _generate_with_llm(
        self,
        session: Session,
        gap_spec: GapSpec,
        capability: str,
        source_task_id: str,
    ) -> ToolRecord:
        """Model-written candidate; schemas stay bound to the gap contract."""
        bus.publish(
            EventType.TOOL_GENERATION_STARTED,
            {"capability": capability, "strategy": "llm", "model": llm_service.model},
        )
        payload = llm_service.generate_tool(gap_spec)
        tool = ToolRecord(
            id=uuid4().hex,
            name=capability,
            description=payload["description"] or gap_spec.description or f"Generated tool for {capability}",
            version="0.1.0",
            status="DRAFT",
            input_schema=dict(gap_spec.input_schema),
            output_schema=dict(gap_spec.output_schema),
            capabilities=[capability],
            tests=payload["tests"],
            source_code=payload["source_code"],
            provenance={
                "strategy": "llm",
                "generation_available": True,
                "source_task_id": source_task_id,
                "gap_spec": gap_spec.model_dump(),
                "model": llm_service.model,
            },
        )
        session.add(tool)
        session.commit()
        session.refresh(tool)
        bus.publish(
            EventType.TOOL_GENERATED,
            {"tool_id": tool.id, "capability": capability, "strategy": "llm"},
        )
        return tool


def sanitize_name(raw: str) -> str:
    """Slugify a capability hint into a safe identifier ('render_a_chart')."""
    words = [w for w in re.split(r"\W+", raw.strip().lower()) if w]
    return "_".join(words) or "undefined_tool"


def _template_source(name: str, gap_spec: GapSpec) -> str:
    inputs = list(gap_spec.input_schema)
    outputs = list(gap_spec.output_schema)
    out_keys = ", ".join(repr(k) for k in outputs)
    return (
        f"def {name}(inputs: dict) -> dict:\n"
        f"    \"\"\"{gap_spec.description or name} — template-generated scaffold.\n"
        f"    Validates declared inputs and echoes them under declared output keys.\n"
        f"    A semantic transform replaces this body when a composition/LLM\n"
        f"    strategy ships.\"\"\"\n"
        f"    required = [{', '.join(repr(k) for k in inputs)}]\n"
        f"    missing = [k for k in required if k not in inputs]\n"
        f"    if missing:\n"
        f"        raise ValueError('missing required inputs: ' + ', '.join(missing))\n"
        f"    return {{k: inputs[k] for k in [{out_keys}] if k in inputs}}\n"
    )


def _generate_tests(name: str, gap_spec: GapSpec) -> list[str]:
    sample = {k: _sample_for(v) for k, v in gap_spec.input_schema.items()}
    tests = [
        f"fn = {name}",
        f"result = fn({sample!r})",
        f"assert isinstance(result, dict)",
    ]
    if gap_spec.output_schema:
        tests.append(f"assert set(result.keys()) <= set({list(gap_spec.output_schema)!r})")
    if not gap_spec.input_schema:
        tests.append(f"assert result == {{}}")
    return tests


def _sample_for(declared: str) -> object:
    """Deterministic sample value for a declared type (later coerced by sandbox)."""
    kind = declared.strip().lower()
    if kind in {"number", "int", "integer", "float"}:
        return 0
    if kind in {"bool", "boolean"}:
        return False
    if kind in {"list", "array"}:
        return []
    if kind in {"dict", "object", "map"}:
        return {}
    return ""


tool_generator = ToolGenerator()
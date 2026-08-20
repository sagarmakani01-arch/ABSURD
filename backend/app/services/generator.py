"""Tool generator — deterministic template strategy (Phase 12).

Given a `GapSpec` from the capability detector, the generator produces a
candidate tool: a plain, valid Python function that validates its declared
inputs and returns its declared outputs. It is an explicit, honest scaffold
("validate + echo"), never a claimed semantic transform — the composition and
LLM strategies that implement real behavior are future work and will replace
the template body.

Candidates enter the registry as DRAFT and must still pass the structural gate
(verify) and activation (register) before the capability detector can use them
to close a gap. Generation is idempotent per capability slug.
"""

from __future__ import annotations

import re
from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.agent.detector import GapSpec
from app.core.tools.registry import tool_registry
from app.events import EventType, bus
from app.models import ToolRecord

# Template-based generation is deterministic and needs no model service.
AVAILABLE_STRATEGIES = ["template"]


class ToolGenerator:
    def generate_available(self) -> bool:
        """True whenever at least one deterministic strategy is registered."""
        return bool(AVAILABLE_STRATEGIES)

    def generate(
        self,
        session: Session,
        gap_spec: GapSpec,
        *,
        source_task_id: str = "",
    ) -> tuple[ToolRecord, bool]:
        """Idempotently create (or return) a DRAFT candidate for a gap spec.

        Returns `(candidate, created)` — `created=False` when a candidate for
        the same capability slug already exists.
        """
        capability = sanitize_name(gap_spec.name_hint or gap_spec.description)
        if tool_registry.by_capability(session, capability):
            return tool_registry.by_capability(session, capability), False

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
        return tool, True


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
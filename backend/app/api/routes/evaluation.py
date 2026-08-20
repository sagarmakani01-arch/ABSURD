"""Evaluation routes: structural + behavioral verification (Phase 13c).

The structural gate (deterministic field/schema checks) and the behavioral
gate (the tool's own tests executed in the sandbox with per-test results)
both run on demand; each failure reports openly with no fabricated scores.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.tools.model import ACTIVATE_REQUIRES
from app.core.tools.registry import tool_registry
from app.db import get_session
from app.events import EventType, bus
from app.models import ToolRecord
from app.services.sandbox import sandbox

router = APIRouter(tags=["evaluation"])

SessionDep = Annotated[Session, Depends(get_session)]


class EvaluationRequest(BaseModel):
    tool_id: str = Field(min_length=1)


def _structural_checks(tool: ToolRecord) -> list[dict[str, object]]:
    checks: list[dict[str, object]] = []
    for field in sorted(ACTIVATE_REQUIRES):
        value = getattr(tool, field)
        present = bool(value if not isinstance(value, str) else value.strip())
        checks.append({"name": f"field.{field}", "passed": present})
    if tool.input_schema and tool.output_schema:
        # JSON Schema shape sanity: values must be strings or dicts, keys non-empty.
        schemas = [("input", tool.input_schema), ("output", tool.output_schema)]
        for name, schema in schemas:
            valid = all(bool(k.strip()) and isinstance(v, (str, dict)) for k, v in schema.items())
            checks.append({"name": f"schema.{name}", "passed": valid, "detail": "types are strings or nested objects" if valid else "invalid schema value types"})
    return checks


@router.post("/evaluations")
def run_evaluation(body: EvaluationRequest, session: SessionDep) -> dict[str, object]:
    """Run the structural gate and the sandbox behavioral gate on a tool."""
    tool = tool_registry.get(session, body.tool_id)
    if tool is None:
        raise HTTPException(status_code=404, detail="tool not found")

    bus.publish(EventType.EVALUATION_STARTED, {"tool_id": tool.id})
    checks = _structural_checks(tool)
    passed = sum(1 for c in checks if c["passed"])
    score = round(passed / len(checks), 3) if checks else 0.0

    behavioral = sandbox.run_tests(tool)
    bus.publish(
        EventType.EVALUATION_FINISHED,
        {
            "tool_id": tool.id,
            "score": score,
            "checks": checks,
            "behavioral_passed": behavioral.get("passed", False),
            "behavioral_error": behavioral.get("error"),
        },
    )

    return {
        "tool_id": tool.id,
        "verification_score": score,
        "checks_passed": passed,
        "checks_total": len(checks),
        "checks": checks,
        "behavioral": behavioral,
    }
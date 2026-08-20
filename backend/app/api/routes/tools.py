"""Tool registry routes (Phase 7)."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.core.agent.detector import GapSpec
from app.core.tools.model import ToolStatus
from app.core.tools.registry import RegistryError, tool_registry
from app.db import get_session
from app.models import ExecutionRecord, ToolRecord
from app.services.generator import GeneratorError, tool_generator
from app.services.sandbox import MAX_TIMEOUT_SECONDS, sandbox

router = APIRouter(tags=["tools"])


class ToolCreate(BaseModel):
    name: str = Field(min_length=1, max_length=256)
    description: str = Field(default="", max_length=4000)
    source_code: str = Field(default="", max_length=200_000)
    dependencies: list[str] = Field(default_factory=list)
    capabilities: list[str] = Field(default_factory=list)
    tests: list[str] = Field(default_factory=list)
    input_schema: dict[str, object] = Field(default_factory=dict)
    output_schema: dict[str, object] = Field(default_factory=dict)


class ToolRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str
    version: str
    status: str
    disabled: bool
    confidence: float
    input_schema: dict[str, object]
    output_schema: dict[str, object]
    source_code: str
    dependencies: list[str]
    capabilities: list[str]
    tests: list[str]
    benchmark_results: dict[str, object]
    security_metadata: dict[str, object]
    provenance: dict[str, object]
    parent_version: str | None
    created_at: datetime
    updated_at: datetime


class GenerateRequest(BaseModel):
    name_hint: str = Field(min_length=1, max_length=256)
    description: str = Field(default="", max_length=4000)
    input_schema: dict[str, str] = Field(default_factory=dict)
    output_schema: dict[str, str] = Field(default_factory=dict)
    security_constraints: list[str] = Field(default_factory=list)


class ToolAction(BaseModel):
    pass


class ExecuteRequest(BaseModel):
    inputs: dict[str, object] = Field(default_factory=dict)
    task_id: str = Field(default="", max_length=64)
    timeout_seconds: float = Field(default=10.0, ge=0.5, le=MAX_TIMEOUT_SECONDS)


class ExecutionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    task_id: str
    tool_id: str
    tool_version: str
    status: str
    input: dict[str, object]
    output: dict[str, object] | None
    error: dict[str, object] | None
    metrics: dict[str, object]
    started_at: datetime
    finished_at: datetime | None


SessionDep = Annotated[Session, Depends(get_session)]


def _get_tool(session: Session, tool_id: str) -> ToolRecord:
    tool = tool_registry.get(session, tool_id)
    if tool is None:
        raise HTTPException(status_code=404, detail="tool not found")
    return tool


def _transition(tool: ToolRecord, target: ToolStatus, session: Session) -> ToolRecord:
    try:
        return tool_registry.transition(session, tool, target)
    except RegistryError as exc:
        raise HTTPException(status_code=422, detail=f"{exc.code}: {str(exc)}") from exc


@router.post("/tools", response_model=ToolRead, status_code=201)
def create_tool(body: ToolCreate, session: SessionDep) -> ToolRecord:
    """Register a new tool as DRAFT. Verification/activation are separate steps."""
    try:
        return tool_registry.create(
            session,
            name=body.name,
            description=body.description,
            source_code=body.source_code,
            capabilities=body.capabilities,
            tests=body.tests,
            input_schema=body.input_schema,
            output_schema=body.output_schema,
            dependencies=body.dependencies,
        )
    except RegistryError as exc:
        raise HTTPException(status_code=422, detail=f"{exc.code}: {str(exc)}") from exc


@router.post("/tools/generate", response_model=ToolRead)
def generate_tool(body: GenerateRequest, session: SessionDep) -> ToolRecord:
    """Generate (or return) a DRAFT candidate from a capability gap spec.

    Uses the deterministic template strategy; idempotent per capability slug.
    The candidate must still pass verify/activate before it closes a gap.
    A capability declared unfillable (candidates rejected repeatedly) is
    refused with 409 instead of generating again.
    """
    try:
        tool, _created = tool_generator.generate(
            session,
            GapSpec(
                name_hint=body.name_hint,
                description=body.description,
                input_schema=body.input_schema,
                output_schema=body.output_schema,
                security_constraints=body.security_constraints,
            ),
        )
    except GeneratorError as exc:
        raise HTTPException(status_code=409, detail={"code": exc.code, "message": exc.message}) from exc
    return tool


@router.get("/tools", response_model=list[ToolRead])
def list_tools(
    session: SessionDep,
    status: Annotated[str | None, Query()] = None,
) -> list[ToolRecord]:
    """Registry contents, optionally filtered by status."""
    return tool_registry.list(session, status=status)


@router.get("/tools/{tool_id}", response_model=ToolRead)
def get_tool(tool_id: str, session: SessionDep) -> ToolRecord:
    return _get_tool(session, tool_id)


@router.post("/tools/{tool_id}/verify", response_model=ToolRead)
def verify_tool(tool_id: str, session: SessionDep, _body: ToolAction | None = None) -> ToolRecord:
    """Structural verification (DRAFT -> VERIFIED). Not behavioral — the
    sandbox phase adds test execution; that is stated in the event payload."""
    return _transition(_get_tool(session, tool_id), ToolStatus.VERIFIED, session)


@router.post("/tools/{tool_id}/activate", response_model=ToolRead)
def activate_tool(tool_id: str, session: SessionDep, _body: ToolAction | None = None) -> ToolRecord:
    """Promote a structurally verified tool to the active registry (REGISTERED)."""
    return _transition(_get_tool(session, tool_id), ToolStatus.REGISTERED, session)


@router.post("/tools/{tool_id}/reject", response_model=ToolRead)
def reject_tool(tool_id: str, session: SessionDep, _body: ToolAction | None = None) -> ToolRecord:
    return _transition(_get_tool(session, tool_id), ToolStatus.REJECTED, session)


@router.post("/tools/{tool_id}/deprecate", response_model=ToolRead)
def deprecate_tool(tool_id: str, session: SessionDep, _body: ToolAction | None = None) -> ToolRecord:
    return _transition(_get_tool(session, tool_id), ToolStatus.DEPRECATED, session)


@router.post("/tools/{tool_id}/disable", response_model=ToolRead)
def disable_tool(tool_id: str, session: SessionDep, _body: ToolAction | None = None) -> ToolRecord:
    """Exclude a tool from planning without changing its lifecycle status.

    The detector never sees disabled tools; re-enable with
    `POST /tools/{tool_id}/enable`.
    """
    return tool_registry.set_disabled(session, _get_tool(session, tool_id), True)


@router.post("/tools/{tool_id}/enable", response_model=ToolRead)
def enable_tool(tool_id: str, session: SessionDep, _body: ToolAction | None = None) -> ToolRecord:
    """Re-include a disabled tool in planning."""
    return tool_registry.set_disabled(session, _get_tool(session, tool_id), False)


@router.get("/capabilities")
def capabilities(session: SessionDep) -> list[dict[str, object]]:
    """Aggregate view of tool coverage per capability domain.

    Drives the Capability Detector's view: every capability declared by any
    tool, with the count of tools declaring it, whether a REGISTERED and
    non-disabled tool covers it, and the matching tool ids.
    """
    by_capability: dict[str, dict[str, object]] = {}
    for tool in tool_registry.list(session):
        for capability in tool.capabilities or []:
            slot = by_capability.setdefault(
                capability,
                {
                    "capability": capability,
                    "tools_total": 0,
                    "registered": [],
                    "covered": False,
                    "disabled": [],
                },
            )
            slot["tools_total"] = int(slot["tools_total"]) + 1
            if tool.status == ToolStatus.REGISTERED.value and not tool.disabled:
                slot["registered"].append(tool.id)
                slot["covered"] = True
            elif tool.disabled:
                slot["disabled"].append(tool.id)
    return sorted(by_capability.values(), key=lambda slot: slot["capability"])


@router.post("/tools/{tool_id}/execute", response_model=ExecutionRead)
def execute_tool(tool_id: str, body: ExecuteRequest, session: SessionDep) -> ExecutionRecord:
    """Run a REGISTERED tool once in the sandbox (Phase 13a).

    The source is policy-checked (AST), executed in an isolated subprocess
    with a wall-clock timeout, and validated against the tool's output
    schema. The result is an honest ExecutionRecord; execution alone does
    not change tool status.
    """
    tool = _get_tool(session, tool_id)
    if tool.status != ToolStatus.REGISTERED.value:
        raise HTTPException(status_code=422, detail="tool not registered")
    return sandbox.execute(
        session,
        tool,
        body.inputs,
        task_id=body.task_id,
        timeout_seconds=body.timeout_seconds,
    )
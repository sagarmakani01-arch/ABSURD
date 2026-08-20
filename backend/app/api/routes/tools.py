"""Tool registry routes (Phase 7)."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.core.tools.model import ToolStatus
from app.core.tools.registry import RegistryError, tool_registry
from app.db import get_session
from app.models import ToolRecord

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


class ToolAction(BaseModel):
    pass


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
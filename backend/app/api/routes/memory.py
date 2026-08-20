"""Memory routes: Experience Memory, Knowledge Graph, Tool Memory aggregates."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import ExperienceRecord, KgEdge
from app.services.memory import experience_memory, knowledge_graph, tool_memory

router = APIRouter(tags=["memory"])

SessionDep = Annotated[Session, Depends(get_session)]


class ExperienceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    kind: str
    task_id: str | None
    input: dict[str, object]
    outcome: str
    result: dict[str, object] | None
    lessons: list[str]
    created_at: datetime


class KgEdgeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    subject: str
    relation: str
    target: str
    payload: dict[str, object]
    created_at: datetime


@router.get("/memory/experience", response_model=list[ExperienceRead])
def list_experiences(
    session: SessionDep,
    kind: Annotated[str | None, Query()] = None,
    outcome: Annotated[str | None, Query()] = None,
    task_id: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[ExperienceRecord]:
    """Append-only Experience Memory, newest first."""
    return experience_memory.query(
        session, kind=kind, outcome=outcome, task_id=task_id, limit=limit
    )


@router.get("/memory/graph", response_model=list[KgEdgeRead])
def list_edges(
    session: SessionDep,
    relation: Annotated[str | None, Query()] = None,
    subject: Annotated[str | None, Query()] = None,
    target: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
) -> list[KgEdge]:
    """Knowledge Graph edges, newest first."""
    return knowledge_graph.query(
        session, relation=relation, subject=subject, target=target, limit=limit
    )


@router.get("/memory/graph/coverage-gaps")
def coverage_gaps(session: SessionDep) -> list[dict[str, object]]:
    """Goals whose required capability still has no registered covering tool."""
    return knowledge_graph.coverage_gaps(session)


@router.get("/memory/tools-usage")
def tools_usage(session: SessionDep) -> dict[str, dict[str, object]]:
    """Tool Memory aggregates: usage count and success rate per tool."""
    return tool_memory.usage(session)
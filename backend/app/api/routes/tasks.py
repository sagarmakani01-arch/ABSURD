"""Task and execution routes (Phase 6 runtime)."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import ExecutionRecord, TaskRecord
from app.services.tasks import task_manager

router = APIRouter(tags=["tasks"])


class TaskCreate(BaseModel):
    goal: str = Field(min_length=1, max_length=2000)
    context: dict[str, object] = Field(default_factory=dict)


class TaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    goal: str
    status: str
    context: dict[str, object]
    result: dict[str, object] | None
    error: dict[str, object] | None
    created_at: datetime
    updated_at: datetime


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


@router.post("/tasks", response_model=TaskRead, status_code=201)
def create_task(body: TaskCreate, session: SessionDep) -> TaskRecord:
    """Submit a task; the agent loop runs it synchronously and verdicts."""
    task = task_manager.create(session, body.goal, body.context)
    return task_manager.run(session, task)


@router.get("/tasks", response_model=list[TaskRead])
def list_tasks(
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    q: Annotated[str | None, Query(max_length=200)] = None,
) -> list[TaskRecord]:
    """Task history, newest first. Optional `q` matches goal or id."""
    return task_manager.list(session, limit=limit, q=q)


@router.get("/tasks/{task_id}", response_model=TaskRead)
def get_task(task_id: str, session: SessionDep) -> TaskRecord:
    task = task_manager.get(session, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    return task


@router.get("/executions", response_model=list[ExecutionRead])
def list_executions(
    session: SessionDep,
    task_id: Annotated[str | None, Query()] = None,
) -> list[ExecutionRecord]:
    """Tool execution history. Empty until the execution pipeline ships (Phase 7)."""
    if task_id:
        return list(session.scalars(select(ExecutionRecord).where(ExecutionRecord.task_id == task_id)))
    return list(session.scalars(select(ExecutionRecord)))
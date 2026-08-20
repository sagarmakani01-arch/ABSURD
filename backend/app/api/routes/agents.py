"""Agent configuration routes (Phase 14).

An agent is a named configuration — plan strategy and retry budget — that
tasks may opt into via `agent_id`. The engine remains fully deterministic;
the configuration only selects among implemented behavior.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import AgentRecord

router = APIRouter(tags=["agents"])

SessionDep = Annotated[Session, Depends(get_session)]

# Only implemented planner strategies are selectable — no pretend modes.
AVAILABLE_STRATEGIES = ["split", "flat"]


class AgentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=256)
    planner_strategy: str = Field(default="split", max_length=32)
    max_retries: int = Field(default=2, ge=0, le=10)


class AgentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    planner_strategy: str
    max_retries: int
    created_at: datetime
    updated_at: datetime


@router.get("/agents", response_model=list[AgentRead])
def list_agents(session: SessionDep) -> list[AgentRecord]:
    return list(session.query(AgentRecord).order_by(AgentRecord.created_at))


@router.post("/agents", response_model=AgentRead, status_code=201)
def create_agent(body: AgentCreate, session: SessionDep) -> AgentRecord:
    if body.planner_strategy not in AVAILABLE_STRATEGIES:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "unsupported_strategy",
                "message": f"planner_strategy must be one of {AVAILABLE_STRATEGIES}",
            },
        )
    agent = AgentRecord(
        id=uuid4().hex,
        name=body.name,
        planner_strategy=body.planner_strategy,
        max_retries=body.max_retries,
    )
    session.add(agent)
    session.commit()
    session.refresh(agent)
    return agent
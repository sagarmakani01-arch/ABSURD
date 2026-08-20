"""Evolution routes: metrics, analysis event log, revision/versioning loop."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import get_session
from app.events import bus
from app.services.evolution import EvolutionError, evolution_service

router = APIRouter(tags=["evolution"])

SessionDep = Annotated[Session, Depends(get_session)]


class RevisionRequest(BaseModel):
    tool_id: str = Field(min_length=1)


class PromotionRequest(BaseModel):
    tool_id: str = Field(min_length=1)
    version: str = Field(min_length=1)


@router.get("/evolution/metrics")
def metrics(session: SessionDep) -> dict[str, object]:
    """Aggregate evolution stats for the dashboard."""
    return evolution_service.metrics(session)


@router.post("/evolution/revisions")
def start_revision(body: RevisionRequest, session: SessionDep) -> dict[str, object]:
    """Begin a tool revision cycle.

    Fails closed with 409 until the LLM generator exists; the attempt is
    recorded on the event stream either way.
    """
    try:
        return evolution_service.start_revision(session, body.tool_id)
    except EvolutionError as exc:
        raise HTTPException(
            status_code=409,
            detail={"code": exc.code, "message": exc.message, "revision_available": False},
        ) from exc


@router.post("/evolution/promotions")
def promote(body: PromotionRequest, session: SessionDep) -> dict[str, object]:
    """Promote a revised candidate version — only after a completed revision."""
    try:
        tool = evolution_service.promote_version(session, body.tool_id, body.version)
    except EvolutionError as exc:
        raise HTTPException(
            status_code=409,
            detail={"code": exc.code, "message": exc.message},
        ) from exc
    return {"tool_id": tool.id, "version": tool.version, "status": tool.status}


@router.get("/evolution/events")
def events(event_type: Annotated[str | None, Query()] = None) -> list[dict[str, object]]:
    """Filtered window over the bus event history (evolution-relevant view)."""
    history = bus.recent(500)
    return [
        {
            "type": e.type.value,
            "payload": e.payload,
            "sequence": e.sequence,
        }
        for e in history
        if event_type is None or e.type.value == event_type
    ]
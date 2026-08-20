"""Evolution routes: metrics and analysis event log."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_session
from app.events import bus
from app.services.evolution import evolution_service

router = APIRouter(tags=["evolution"])

SessionDep = Annotated[Session, Depends(get_session)]


@router.get("/evolution/metrics")
def metrics(session: SessionDep) -> dict[str, object]:
    """Aggregate evolution stats for the dashboard."""
    return evolution_service.metrics(session)


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
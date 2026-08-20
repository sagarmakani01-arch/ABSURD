"""Event history route — serves the bus ring buffer as `GET /api/v1/events`."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from app.events import bus

router = APIRouter(tags=["system"])


@router.get("/events")
def list_events(limit: Annotated[int, Query(ge=1, le=500)] = 100) -> list[dict[str, object]]:
    """Most recent bus events in publication order (autoincremented seq)."""
    return [
        {
            "id": event.id,
            "type": event.type.value,
            "payload": event.payload,
            "sequence": event.sequence,
        }
        for event in bus.recent(limit)
    ]
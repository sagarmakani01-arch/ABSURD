"""Health and system status routes."""

from __future__ import annotations

from fastapi import APIRouter

from app import __version__
from app.events import EventType, bus

router = APIRouter(tags=["system"])


@router.get("/health")
async def health() -> dict[str, object]:
    """Liveness probe — gateway is up and its event bus is live."""
    return {
        "status": "ok",
        "service": "absurd",
        "version": __version__,
        "event_bus": "live",
    }


@router.post("/system/events/probe")
async def probe_event() -> dict[str, object]:
    """Emit a SYSTEM_STARTED event on the bus; used to smoke-test WS bridging."""
    event = bus.publish(EventType.SYSTEM_STARTED, {"source": "api"})
    return {"event_id": event.id, "sequence": event.sequence}
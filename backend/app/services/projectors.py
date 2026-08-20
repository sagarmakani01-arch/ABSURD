"""Event projectors — the memory stores are projections of the event stream.

Attached to the bus once at import time (see main.py). Each projector opens
its own session so writes never depend on the request's transaction, and each
handler is invoked only for the event types it owns. They must never raise
into the publisher — memory is best-effort observability.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from sqlalchemy.orm import Session

from app.events import Event, EventType
from app.models import ToolRecord
from app.services.memory import REL_ENABLES, REL_REQUIRES, experience_memory, knowledge_graph

logger = logging.getLogger("absurd.projectors")


def _session_factory() -> Session:
    from app.db import SessionLocal

    return SessionLocal()


def install() -> None:
    """Attach memory projectors to the application event bus."""
    from app.events import bus

    bus.subscribe(_dispatch)


def _dispatch(event: Event) -> None:
    handler = _HANDLERS.get(event.type)
    if handler is None:
        return
    session: Session | None = None
    try:
        session = _session_factory()
        handler(session, event)
    except Exception:  # pragma: no cover - defensive
        logger.exception("projector failed for event %s", event.type)
    finally:
        if session is not None:
            session.close()


def _write_task_success(session: Session, event: Event) -> None:
    task_id = str(event.payload.get("task_id", ""))
    experience_memory.add(
        session,
        kind="task",
        outcome="success",
        task_id=task_id,
        input_data={"event_sequence": event.sequence},
    )


def _write_task_failure(session: Session, event: Event) -> None:
    task_id = str(event.payload.get("task_id", ""))
    kind = str(event.payload.get("kind", "unknown"))
    missing = list(event.payload.get("missing") or [])
    payload = {k: v for k, v in event.payload.items() if k != "task_id"}
    lessons = [f"missing capability: {m}" for m in missing]
    if not event.payload.get("generation_available", True):
        lessons.append("tool generation unavailable")
    experience_memory.add(
        session,
        kind="task",
        outcome="failure",
        task_id=task_id,
        input_data={"event_sequence": event.sequence},
        result={"kind": kind, **payload},
        lessons=lessons,
    )
    # Evolution loop: deterministic classification + block edges + event.
    from app.services.evolution import evolution_service

    evolution_service.analyze_failure(session, event.payload)
    session.commit()


def _write_requires_edges(session: Session, event: Event) -> None:
    task_id = str(event.payload.get("task_id", ""))
    for gap in event.payload.get("gaps") or []:
        knowledge_graph.add_edge(
            session,
            subject=f"task:{task_id}",
            relation=REL_REQUIRES,
            target=f"capability:{gap}",
            payload={"generation_available": event.payload.get("generation_available", False)},
        )


def _write_enables_edges(session: Session, event: Event) -> None:
    tool = session.get(ToolRecord, str(event.payload.get("tool_id", "")))
    if tool is None:
        return
    for capability in tool.capabilities or []:
        knowledge_graph.add_edge(
            session,
            subject=f"tool:{tool.id}",
            relation=REL_ENABLES,
            target=f"capability:{capability}",
            payload={"version": tool.version},
        )


# Each owned event type is handled by exactly one projection function.
_HANDLERS: dict[EventType, Callable[[Session, Event], None]] = {
    EventType.TASK_COMPLETED: _write_task_success,
    EventType.TASK_FAILED: _write_task_failure,
    EventType.CAPABILITY_GAP_DETECTED: _write_requires_edges,
    EventType.TOOL_REGISTERED: _write_enables_edges,
}
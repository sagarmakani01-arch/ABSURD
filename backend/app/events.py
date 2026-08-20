"""Event system.

Every major state transition in ABSURD emits a typed event. The WebSocket
bridge streams these to the frontend so the UI can reconstruct the complete
execution history. This module defines the canonical event vocabulary.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

EVENT_VERSION = 1


class EventType(StrEnum):
    """Canonical ABSURD event vocabulary."""

    # Task lifecycle
    TASK_CREATED = "task.created"
    TASK_ANALYZED = "task.analyzed"
    TASK_COMPLETED = "task.completed"
    TASK_FAILED = "task.failed"
    TASK_CANCELLED = "task.cancelled"

    # Capability detection
    CAPABILITY_CHECK_STARTED = "capability.check_started"
    CAPABILITY_REQUIRED = "capability.required"
    CAPABILITY_FOUND = "capability.found"
    CAPABILITY_MISSING = "capability.missing"
    CAPABILITY_GAP_DETECTED = "capability.gap_detected"
    CAPABILITY_ACQUIRED = "capability.acquired"

    # Tool lifecycle
    TOOL_SELECTED = "tool.selected"
    TOOL_GENERATION_STARTED = "tool.generation_started"
    TOOL_GENERATION_REQUESTED = "tool.generation_requested"
    TOOL_GENERATED = "tool.generated"
    TOOL_REVISED = "tool.revised"
    TOOL_VERIFIED = "tool.verified"
    TOOL_REGISTERED = "tool.registered"
    TOOL_REJECTED = "tool.rejected"
    TOOL_DEPRECATED = "tool.deprecated"
    TOOL_DISABLED = "tool.disabled"
    TOOL_ENABLED = "tool.enabled"
    TOOL_EXECUTION_STARTED = "tool.execution_started"
    TOOL_EXECUTION_FINISHED = "tool.execution_finished"

    # Sandbox
    SANDBOX_STARTED = "sandbox.started"
    SANDBOX_TIMEOUT = "sandbox.timeout"
    SECURITY_VIOLATION = "sandbox.security_violation"
    EXECUTION_FAILED = "sandbox.execution_failed"
    EXECUTION_COMPLETED = "sandbox.execution_completed"

    # Evaluation
    EVALUATION_STARTED = "evaluation.started"
    EVALUATION_FINISHED = "evaluation.finished"
    TEST_FAILED = "evaluation.test_failed"
    TEST_PASSED = "evaluation.test_passed"

    # Evolution
    TOOL_REVISION_STARTED = "evolution.revision_started"
    TOOL_REVISION_FAILED = "evolution.revision_failed"
    TOOL_REVISION_IMPROVED = "evolution.revision_improved"
    TOOL_VERSION_PROMOTED = "evolution.version_promoted"
    FAILURE_ANALYZED = "failure.analyzed"
    PLAN_REVISED = "plan.revised"
    TOOL_QUARANTINED = "tool.quarantined"
    CAPABILITY_GAP_UNFILLABLE = "capability.gap_unfillable"

    # System
    SYSTEM_STARTED = "system.started"


class Event(BaseModel):
    """An internal domain event.

    Every event carries a monotonic sequence number assigned by the bus, a
    UUID, a timestamp, and a structured payload. Payloads must be JSON
    serializable and are governed by per-type schema validation downstream.
    """

    id: str = Field(default_factory=lambda: uuid4().hex)
    type: EventType
    payload: dict[str, Any] = Field(default_factory=dict)
    sequence: int = 0
    timestamp: str | None = None


HISTORY_LIMIT = 500


class EventBus:
    """In-process publish/subscribe event bus.

    Synchronous subscriber dispatch. The bus keeps a bounded in-memory ring
    buffer of recent events so the API can serve `GET /api/v1/events`;
    long-term persistence is the job of the memory layer (Experience Memory).
    """

    def __init__(self) -> None:
        self._subscribers: list[callable] = []
        self._history: list[Event] = []
        self._sequence = 0

    def subscribe(self, handler: callable) -> None:
        """Register a callable receiving every event."""
        self._subscribers.append(handler)

    def recent(self, limit: int = 100) -> list[Event]:
        """Most recent events in publication order (bounded ring buffer)."""
        return list(self._history[-limit:])

    def reset(self) -> None:
        """Clear history and sequence (test isolation; never used by the app)."""
        self._history.clear()
        self._sequence = 0

    def publish(self, event_type: EventType, payload: dict[str, Any] | None = None) -> Event:
        """Create and dispatch an event synchronously."""
        self._sequence += 1
        event = Event(type=event_type, payload=payload or {}, sequence=self._sequence)
        self._history.append(event)
        if len(self._history) > HISTORY_LIMIT:
            del self._history[:-HISTORY_LIMIT]
        for handler in list(self._subscribers):
            handler(event)
        return event


# Application-wide singleton.
bus = EventBus()
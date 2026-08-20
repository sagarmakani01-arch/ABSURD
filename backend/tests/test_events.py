"""Unit tests for the event system."""

from __future__ import annotations

from app.events import EventBus, EventType


def test_event_sequence_monotonic() -> None:
    bus = EventBus()
    first = bus.publish(EventType.SYSTEM_STARTED)
    second = bus.publish(EventType.CAPABILITY_REQUIRED, {"capability": "x"})
    assert first.sequence < second.sequence
    assert second.payload == {"capability": "x"}


def test_subscribers_receive_all_events() -> None:
    bus = EventBus()
    seen: list[str] = []
    bus.subscribe(lambda event: seen.append(event.type.value))
    bus.publish(EventType.TASK_CREATED)
    bus.publish(EventType.TOOL_GENERATED)
    assert seen == [EventType.TASK_CREATED.value, EventType.TOOL_GENERATED.value]


def test_event_type_vocabulary_is_stable() -> None:
    required = {
        "task.created",
        "capability.gap_detected",
        "tool.generation_started",
        "tool.registered",
        "capability.acquired",
        "task.completed",
    }
    assert required <= {t.value for t in EventType}
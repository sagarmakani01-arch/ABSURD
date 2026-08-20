"""Phase 14 tests: maintenance sweeps — confidence decay, retention, pruning, PII."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.main import app
from app.models import ExperienceRecord, KgEdge, ToolRecord
from app.services.maintenance import run_maintenance
from app.services.memory import experience_memory, knowledge_graph, redact_pii
from app.services.tasks import task_manager

client = TestClient(app)

SAMPLE = {
    "description": "Sums two numbers.",
    "source_code": "def sum_tool(inputs: dict) -> dict:\n    return {'sum': int(inputs.get('a', 0)) + int(inputs.get('b', 0))}\n",
    "input_schema": {"a": "number", "b": "number"},
    "output_schema": {"sum": "number"},
    "capabilities": ["sum_tool"],
    "tests": ["fn = sum_tool", "result = fn({'a': 1, 'b': 2})", "assert isinstance(result, dict)"],
}


def _registered_tool() -> ToolRecord:
    with SessionLocal() as session:
        from app.core.tools.registry import tool_registry

        return tool_registry.create(
            session,
            name="sum_tool",
            description=SAMPLE["description"],
            source_code=SAMPLE["source_code"],
            capabilities=["sum_tool"],
            tests=SAMPLE["tests"],
            input_schema=SAMPLE["input_schema"],
            output_schema=SAMPLE["output_schema"],
            dependencies=[],
        )


def _aged_row(row: object, *, status: str, days: int, confidence: float = 0.1) -> None:
    with SessionLocal() as session:
        obj = session.merge(row)
        obj.status = status
        obj.confidence = confidence
        obj.updated_at = datetime.now(timezone.utc) - timedelta(days=days)
        if isinstance(obj, KgEdge):
            obj.created_at = datetime.now(timezone.utc) - timedelta(days=days)
        session.commit()


def test_confidence_halves_per_unused_window() -> None:
    tool = _registered_tool()
    _aged_row(tool, status="REGISTERED", days=32, confidence=0.8)  # one 30-day window
    with SessionLocal() as session:
        run_maintenance(session)
    with SessionLocal() as session:
        assert session.get(ToolRecord, tool.id).confidence == 0.4


def test_deprecated_tools_purged_after_retention() -> None:
    tool = _registered_tool()
    _aged_row(tool, status="DEPRECATED", days=200)  # past the 180-day window
    with SessionLocal() as session:
        counts = run_maintenance(session)
    assert counts["tools_purged"] == 1
    with SessionLocal() as session:
        assert session.get(ToolRecord, tool.id) is None


def test_recent_deprecated_tool_retained() -> None:
    tool = _registered_tool()
    _aged_row(tool, status="DEPRECATED", days=3)
    with SessionLocal() as session:
        counts = run_maintenance(session)
    assert counts["tools_purged"] == 0


def test_stale_edges_pruned_when_oriented() -> None:
    with SessionLocal() as session:
        old = knowledge_graph.add_edge(session, subject="capability:legacy", relation="requires", target="task:t1")
        newer = knowledge_graph.add_edge(session, subject="capability:keeper", relation="requires", target="task:t2")
    _aged_row(old, status="REGISTERED", days=120)
    _aged_row(newer, status="REGISTERED", days=2)
    with SessionLocal() as session:
        counts = run_maintenance(session)
    assert counts["kg_edges_pruned"] == 1  # `old` has no recently-touched node
    with SessionLocal() as session:
        assert len(knowledge_graph.query(session)) == 1


def test_pii_keys_redacted_at_experience_write() -> None:
    with SessionLocal() as session:
        exp = experience_memory.add(
            session,
            kind="task",
            outcome="success",
            input_data={"recipient": "ops@example.com", "api_key": "sk-secret", "nested": {"password": "hunter2"}},
            result={"token": "abc123"},
        )
    assert exp.input["recipient"] == "ops@example.com"
    assert exp.input["api_key"] == "[REDACTED]"
    assert exp.input["nested"]["password"] == "[REDACTED]"
    assert exp.result["token"] == "[REDACTED]"
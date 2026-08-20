"""Phase 14 tests: task cancellation — REST route, engine honouring, WS."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app.core.agent.engine import agent_engine
from app.db import SessionLocal
from app.main import app
from app.models import ExecutionRecord, TaskRecord
from app.services.tasks import task_manager

client = TestClient(app)


def test_cancel_requires_existing_task() -> None:
    assert client.post("/api/v1/tasks/nope/cancel").status_code == 404


def test_cancel_inflight_task() -> None:
    """REST create runs the agent loop synchronously, so a cancel-worthy task
    is created without running it first (the WS/worker path)."""
    with SessionLocal() as session:
        task = task_manager.create(session, "long running goal", {})
        task_id = task.id

    cancelled = client.post(f"/api/v1/tasks/{task_id}/cancel")
    assert cancelled.status_code == 200
    body = cancelled.json()
    assert body["status"] == "CANCELLED"

    events = [e["type"] for e in client.get("/api/v1/events").json()]
    assert "task.cancelled" in events


def test_terminal_tasks_cannot_be_cancelled() -> None:
    created = client.post("/api/v1/tasks", json={"goal": "compute the sum", "context": {}}).json()
    assert created["status"] in {"COMPLETED", "FAILED"}

    with SessionLocal() as session:
        task = task_manager.cancel(session, created["id"])
    assert task is not None and task.status != "CANCELLED"

    again = client.post(f"/api/v1/tasks/{created['id']}/cancel")
    assert again.status_code == 422


def test_engine_honours_cancel_before_running() -> None:
    """A task cancelled before its agent loop starts never executes a step."""
    with SessionLocal() as session:
        task = task_manager.create(session, "use any tool", {})
        task_id = task.id
        cancelled = task_manager.cancel(session, task_id)
        assert cancelled is not None and cancelled.status == "CANCELLED"

    with SessionLocal() as session:
        again = session.get(TaskRecord, task_id)
        agent_engine.run(session, again)
        assert again.status == "CANCELLED"
        assert not list(session.query(ExecutionRecord))


def test_ws_cancel_replies_task_cancelled() -> None:
    with SessionLocal() as session:
        task = task_manager.create(session, "compute the sum", {})
        task_id = task.id
    with client.websocket_connect("/ws") as ws:
        ws.send_text(json.dumps({"type": "task.cancel", "payload": {"task_id": task_id}}))
        reply = ws.receive_json()
        assert reply["type"] == "task.cancelled"
        assert reply["payload"]["status"] == "CANCELLED"


def test_ws_cancel_unknown_task_errors() -> None:
    with client.websocket_connect("/ws") as ws:
        ws.send_text(json.dumps({"type": "task.cancel", "payload": {"task_id": "missing"}}))
        reply = ws.receive_json()
        assert reply["type"] == "error"
        assert reply["payload"]["code"] == "task_not_found"
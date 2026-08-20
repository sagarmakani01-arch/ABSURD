"""Runtime phase tests: task lifecycle, capability verdicts, event history."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _submit(goal: str) -> dict[str, object]:
    response = client.post("/api/v1/tasks", json={"goal": goal, "context": {}})
    assert response.status_code == 201
    return response.json()


def test_submit_task_fails_honestly_with_no_capability() -> None:
    """Registry is empty in Phase 6 — failure must be explicit and structured."""
    body = _submit("compute the fibonacci sequence")
    assert body["status"] == "FAILED"
    error = body["error"]
    assert error["kind"] == "NO_CAPABILITY"
    assert isinstance(error["missing"], list)
    assert error["missing"]


def test_task_list_and_get() -> None:
    created = _submit("sort a list of numbers")
    listed = client.get("/api/v1/tasks").json()
    assert any(t["id"] == created["id"] for t in listed)
    fetched = client.get(f"/api/v1/tasks/{created['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["goal"] == "sort a list of numbers"
    assert client.get("/api/v1/tasks/nope").status_code == 404


def test_task_list_search() -> None:
    _submit("fetch weather data")
    hits = client.get("/api/v1/tasks", params={"q": "weather"}).json()
    assert hits and hits[0]["goal"] == "fetch weather data"
    assert client.get("/api/v1/tasks", params={"q": "zzz-nomatch"}).json() == []


def test_task_events_emitted_in_order() -> None:
    _submit("generate a pdf report")
    types = [e["type"] for e in client.get("/api/v1/events", params={"limit": 50}).json()]
    expected = ["task.created", "task.analyzed", "capability.check_started", "capability.gap_detected", "task.failed"]
    positions = [types.index(t) for t in expected]
    assert positions == sorted(positions)
    sequences = [e["sequence"] for e in client.get("/api/v1/events").json()]
    assert sequences == sorted(sequences)


def test_executions_empty_until_phase7() -> None:
    task = _submit("parse a csv file")
    assert client.get("/api/v1/executions").json() == []
    assert client.get("/api/v1/executions", params={"task_id": task["id"]}).json() == []
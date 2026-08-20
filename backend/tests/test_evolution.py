"""Phase 10 tests: revision/versioning loop and evolution metrics."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.events import EventType, bus
from app.main import app

client = TestClient(app)

SAMPLE = {
    "name": "calculator",
    "description": "Arithmetic operations over input numbers.",
    "source_code": "def add(a, b):\n    return a + b\n",
    "capabilities": ["arithmetic"],
    "tests": ["assert add(1, 2) == 3"],
    "input_schema": {"a": "number", "b": "number"},
    "output_schema": {"result": "number"},
}


def _register_and_activate() -> dict[str, object]:
    tool = client.post("/api/v1/tools", json=SAMPLE).json()
    client.post(f"/api/v1/tools/{tool['id']}/verify")
    client.post(f"/api/v1/tools/{tool['id']}/activate")
    return tool


def test_revision_unavailable_until_generator() -> None:
    tool = _register_and_activate()
    resp = client.post("/api/v1/evolution/revisions", json={"tool_id": tool["id"]})
    assert resp.status_code == 409
    body = resp.json()["detail"]
    assert body["code"] == "revision_generation_unavailable"
    assert body["revision_available"] is False

    types = [e["type"] for e in client.get("/api/v1/evolution/events").json()]
    assert "evolution.revision_started" in types
    assert "evolution.revision_failed" in types


def test_revision_rejects_non_registered_tool() -> None:
    draft = client.post("/api/v1/tools", json=SAMPLE).json()
    resp = client.post("/api/v1/evolution/revisions", json={"tool_id": draft["id"]})
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "illegal_state"


def test_promotion_requires_completed_revision() -> None:
    tool = _register_and_activate()
    resp = client.post(
        "/api/v1/evolution/promotions",
        json={"tool_id": tool["id"], "version": "0.2.0"},
    )
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "no_completed_revision"


def test_promotion_after_successful_revision() -> None:
    tool = _register_and_activate()
    bus.publish(
        EventType.TOOL_REVISION_IMPROVED,
        {"tool_id": tool["id"], "from_version": "0.1.0", "to_version": "0.2.0"},
    )
    resp = client.post(
        "/api/v1/evolution/promotions",
        json={"tool_id": tool["id"], "version": "0.2.0"},
    )
    assert resp.status_code == 200
    assert resp.json()["version"] == "0.2.0"

    read = client.get(f"/api/v1/tools/{tool['id']}").json()
    assert read["version"] == "0.2.0"

    types = [e["type"] for e in client.get("/api/v1/evolution/events").json()]
    assert "evolution.version_promoted" in types


def test_metrics_report_gap_closure_and_revision_state() -> None:
    before = client.get("/api/v1/evolution/metrics").json()
    client.post("/api/v1/tasks", json={"goal": "render a chart", "context": {}}).json()
    after = client.get("/api/v1/evolution/metrics").json()
    assert after["gap_close_rate"] == 0.0
    assert after["revisions_total"] == before["revisions_total"]
    assert after["revision_available"] is False

    bus.publish(EventType.TOOL_REVISION_STARTED, {"tool_id": "x"})
    with_revision = client.get("/api/v1/evolution/metrics").json()
    assert with_revision["revisions_total"] == before["revisions_total"] + 1

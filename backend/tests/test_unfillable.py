"""Phase 14 tests: unfillable gaps — rejected candidates short-circuit generation."""

from __future__ import annotations

from fastapi.testclient import TestClient

import app.config as config
from app.main import app

client = TestClient(app)

GAP = {
    "name_hint": "brittle_parser",
    "description": "Parses something that keeps failing.",
    "input_schema": {"text": "str"},
    "output_schema": {"parsed": "str"},
}


def _generate_and_reject() -> None:
    tool = client.post("/api/v1/tools/generate", json=GAP)
    assert tool.status_code == 200, tool.text
    candidate = tool.json()
    assert candidate["status"] == "DRAFT"
    assert client.post(f"/api/v1/tools/{candidate['id']}/reject").status_code == 200


def test_unfillable_after_threshold_rejections() -> None:
    assert config.UNFILLABLE_GAP_THRESHOLD == 2
    _generate_and_reject()
    _generate_and_reject()

    refused = client.post("/api/v1/tools/generate", json=GAP)
    assert refused.status_code == 409
    assert refused.json()["detail"]["code"] == "capability_unfillable"

    events = [e for e in client.get("/api/v1/events").json() if e["type"] == "capability.gap_unfillable"]
    assert len(events) == 1
    assert events[0]["payload"]["rejected_count"] == 2


def test_unfillable_gap_skips_seeding_and_fails_honestly() -> None:
    """A task needing an unfillable capability fails NO_CAPABILITY without
    producing another futile DRAFT candidate."""
    _generate_and_reject()
    _generate_and_reject()

    task = client.post(
        "/api/v1/tasks",
        json={
            "goal": "brittle parser",
            "context": {"expected_io": [{"inputs": {"text": "str"}, "outputs": {"parsed": "str"}}]},
        },
    ).json()
    assert task["status"] == "FAILED"
    assert task["error"]["kind"] == "NO_CAPABILITY"
    assert task["error"]["attempts"] == 1

    tools = client.get("/api/v1/tools", params={"status": "DRAFT"}).json()
    assert tools == []  # no new candidate seeded for the unfillable gap

    edges = client.get("/api/v1/memory/graph").json()
    unfillable = [e for e in edges if e["relation"] == "unfillable"]
    assert len(unfillable) == 1  # recorded once the engine meets the dead gap

    metrics = client.get("/api/v1/evolution/metrics").json()
    assert metrics["unfillable_gaps"] >= 1
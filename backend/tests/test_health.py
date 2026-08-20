"""Smoke tests for the gateway foundation."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health() -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "absurd"


def test_health_is_live() -> None:
    """Two calls in one client session prove the event bus stays live."""
    assert client.get("/api/v1/health").json()["event_bus"] == "live"


def test_probe_event_emits() -> None:
    response = client.post("/api/v1/system/events/probe")
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body["event_id"], str)
    assert body["sequence"] > 0
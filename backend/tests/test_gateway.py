"""Phase 14 tests: gateway hardening — request-id, rate limit, payload cap."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import app.config as config
from app.main import app

client = TestClient(app)


@pytest.fixture()
def tight_gateway():
    """Tiny rate limit + small payload cap so tests trigger them quickly."""
    config.RATE_LIMIT_PER_MINUTE = 2
    config.MAX_REQUEST_BYTES = 120
    yield
    config.RATE_LIMIT_PER_MINUTE = 0
    config.MAX_REQUEST_BYTES = 262144


def test_request_id_generated_and_echoed() -> None:
    response = client.get("/api/v1/health")
    assert response.headers["X-Request-ID"] != ""


def test_inbound_request_id_preserved() -> None:
    response = client.get("/api/v1/health", headers={"X-Request-ID": "trace-123"})
    assert response.headers["X-Request-ID"] == "trace-123"


def test_rate_limit_rejects_burst(tight_gateway) -> None:
    assert client.get("/api/v1/health").status_code == 200  # exempt
    first = client.get("/api/v1/tools")
    second = client.get("/api/v1/tools")
    third = client.get("/api/v1/tools")
    assert first.status_code == 200
    assert second.status_code == 200
    assert third.status_code == 429
    assert third.json()["code"] == "rate_limited"


def test_health_exempt_from_rate_limit(tight_gateway) -> None:
    for _ in range(6):
        assert client.get("/api/v1/health").status_code == 200


def test_payload_cap_rejects_large_body(tight_gateway) -> None:
    big_goal = "x" * 1000
    response = client.post("/api/v1/tasks", json={"goal": big_goal, "context": {}})
    assert response.status_code == 413
    assert response.json()["code"] == "payload_too_large"


def test_payload_cap_allows_small_body(tight_gateway) -> None:
    response = client.post("/api/v1/tasks", json={"goal": "compute the sum", "context": {}})
    assert response.status_code == 201
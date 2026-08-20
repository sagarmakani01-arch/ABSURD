"""Phase 13f tests: REST Bearer-token auth, on only when a token is set."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

import app.config as config
from app.main import app

client = TestClient(app)


@pytest.fixture()
def auth_enabled():
    config.API_TOKEN = "test-secret-token"
    yield
    config.API_TOKEN = ""


def test_open_by_default() -> None:
    assert config.API_TOKEN == ""
    response = client.post("/api/v1/tasks", json={"goal": "compute the sum", "context": {}})
    assert response.status_code == 201


def test_health_and_docs_remain_public(auth_enabled) -> None:
    assert client.get("/api/v1/health").status_code == 200
    assert client.get("/api/v1/health").json()["status"] == "ok"
    assert client.get("/docs").status_code == 200
    assert client.get("/openapi.json").status_code == 200


def test_api_requires_bearer_token(auth_enabled) -> None:
    assert client.post("/api/v1/tasks", json={"goal": "x", "context": {}}).status_code == 401
    assert client.get("/api/v1/tools").status_code == 401
    assert client.get("/api/v1/evolution/metrics").status_code == 401


def test_wrong_token_rejected(auth_enabled) -> None:
    headers = {"Authorization": "Bearer wrong"}
    assert client.get("/api/v1/tools", headers=headers).status_code == 401


def test_valid_token_authorized(auth_enabled) -> None:
    headers = {"Authorization": "Bearer test-secret-token"}
    assert client.post(
        "/api/v1/tasks", json={"goal": "compute the sum", "context": {}}, headers=headers
    ).status_code == 201
    assert client.get("/api/v1/evolution/metrics", headers=headers).status_code == 200


def test_websocket_rejects_missing_token(auth_enabled) -> None:
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect("/ws"):
            pass
    assert exc.value.code == 1008


def test_websocket_accepts_query_token(auth_enabled) -> None:
    with client.websocket_connect("/ws?token=test-secret-token") as ws:
        ws.send_text("hello")
        assert ws.receive_json()["type"] == "pong"


def test_websocket_accepts_header_token(auth_enabled) -> None:
    with client.websocket_connect(
        "/ws", headers={"Authorization": "Bearer test-secret-token"}
    ) as ws:
        ws.send_text("hello")
        assert ws.receive_json()["type"] == "pong"
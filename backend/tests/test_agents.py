"""Phase 14 tests: agent configurations drive the retry budget."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

SAMPLE = {
    "description": "Crashes on every call.",
    "source_code": "def crashing_tool(inputs: dict) -> dict:\n    raise ValueError('nope')\n",
    "input_schema": {"a": "number"},
    "output_schema": {"b": "number"},
    "capabilities": ["crashing_tool"],
    "tests": ["fn = crashing_tool", "result = fn({})"],
}


def _register_crashing() -> str:
    tool = client.post("/api/v1/tools", json={"name": "crashing_tool", **SAMPLE}).json()
    client.post(f"/api/v1/tools/{tool['id']}/verify")
    client.post(f"/api/v1/tools/{tool['id']}/activate")
    return tool["id"]


def test_agents_empty_by_default() -> None:
    assert client.get("/api/v1/agents").json() == []


def test_create_agent_roundtrip() -> None:
    created = client.post(
        "/api/v1/agents",
        json={"name": "conservative", "planner_strategy": "split", "max_retries": 1},
    )
    assert created.status_code == 201
    agent = created.json()
    assert agent["name"] == "conservative"
    assert agent["planner_strategy"] == "split"
    assert agent["max_retries"] == 1

    listing = client.get("/api/v1/agents").json()
    assert [a["id"] for a in listing] == [agent["id"]]


def test_unsupported_strategy_rejected() -> None:
    response = client.post(
        "/api/v1/agents",
        json={"name": "sci-fi", "planner_strategy": "hierarchical", "max_retries": 2},
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "unsupported_strategy"


def test_max_retries_zero_means_no_replan() -> None:
    tool_id = _register_crashing()
    agent = client.post(
        "/api/v1/agents",
        json={"name": "no-retry", "planner_strategy": "split", "max_retries": 0},
    ).json()

    task = client.post(
        "/api/v1/tasks",
        json={
            "goal": "use the crashing tool",
            "context": {"inputs": [{"a": 1}]},
            "agent_id": agent["id"],
        },
    ).json()
    assert task["status"] == "FAILED"
    assert task["error"]["kind"] == "TOOL_EXECUTION_FAILED"
    assert task["error"]["attempts"] == 1

    events = [e["type"] for e in client.get("/api/v1/events").json()]
    assert "plan.revised" not in events

    usage = client.get("/api/v1/memory/tools-usage").json()
    assert usage[tool_id]["usage_count"] == 1


def test_retries_emit_plan_revised_and_exhaust_budget() -> None:
    _register_crashing()
    agent = client.post(
        "/api/v1/agents",
        json={"name": "patient", "planner_strategy": "split", "max_retries": 2},
    ).json()

    task = client.post(
        "/api/v1/tasks",
        json={
            "goal": "use the crashing tool",
            "context": {"inputs": [{"a": 1}]},
            "agent_id": agent["id"],
        },
    ).json()
    assert task["status"] == "FAILED"
    assert task["error"]["attempts"] == 3

    events = [e for e in client.get("/api/v1/events").json()]
    revised = [e for e in events if e["type"] == "plan.revised"]
    assert len(revised) == 2


def test_ws_task_create_runs_and_acknowledges() -> None:
    tool_id = _register_crashing()
    with client.websocket_connect("/ws") as ws:
        ws.send_text(json.dumps({"type": "task.create", "payload": {"goal": "use the crashing tool", "context": {"inputs": [{"a": 1}]}}}))
        accepted = ws.receive_json()
        assert accepted["type"] == "task.accepted"
        task_id = accepted["payload"]["task_id"]

        ws.send_text(json.dumps({"type": "ping", "payload": {}}))
        assert ws.receive_json()["type"] == "pong"

    task = client.get(f"/api/v1/tasks/{task_id}").json()
    assert task["status"] == "FAILED"
    assert task["error"]["kind"] == "TOOL_EXECUTION_FAILED"
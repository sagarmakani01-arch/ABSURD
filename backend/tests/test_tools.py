"""Tool registry phase tests: lifecycle, transitions, capability impact."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

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


def _register(**overrides) -> dict[str, object]:
    body = {**SAMPLE, **overrides}
    response = client.post("/api/v1/tools", json=body)
    assert response.status_code == 201
    return response.json()


def test_create_tool_as_draft() -> None:
    tool = _register()
    assert tool["status"] == "DRAFT"
    assert tool["version"] == "0.1.0"
    assert tool["name"] == "calculator"


def test_create_rejects_empty_name() -> None:
    response = client.post("/api/v1/tools", json={**SAMPLE, "name": "   "})
    assert response.status_code == 422


def test_verify_requires_content() -> None:
    tool = _register(source_code="", tests=[])
    response = client.post(f"/api/v1/tools/{tool['id']}/verify")
    assert response.status_code == 422
    assert "source_code" in response.json()["detail"]


def test_full_lifecycle() -> None:
    tool = _register()
    tid = tool["id"]

    verified = client.post(f"/api/v1/tools/{tid}/verify")
    assert verified.status_code == 200
    assert verified.json()["status"] == "VERIFIED"

    activated = client.post(f"/api/v1/tools/{tid}/activate")
    assert activated.status_code == 200
    assert activated.json()["status"] == "REGISTERED"

    deprecated = client.post(f"/api/v1/tools/{tid}/deprecate")
    assert deprecated.status_code == 200
    assert deprecated.json()["status"] == "DEPRECATED"


def test_illegal_transition_422() -> None:
    tool = _register()
    # DRAFT -> REGISTERED without verifying is illegal.
    response = client.post(f"/api/v1/tools/{tool['id']}/activate")
    assert response.status_code == 422


def test_activate_requires_complete_spec() -> None:
    tool = _register(capabilities=[])
    # Capabilities are a REGISTERED-gate requirement: verify passes, activate blocks.
    assert client.post(f"/api/v1/tools/{tool['id']}/verify").status_code == 200
    response = client.post(f"/api/v1/tools/{tool['id']}/activate")
    assert response.status_code == 422
    assert "capabilities" in response.json()["detail"]
    found = client.get(f"/api/v1/tools/{tool['id']}").json()
    assert found["status"] == "VERIFIED"


def test_list_and_get() -> None:
    _register()
    items = client.get("/api/v1/tools").json()
    assert any(t["name"] == "calculator" for t in items)
    drafts = client.get("/api/v1/tools", params={"status": "DRAFT"}).json()
    assert all(t["status"] == "DRAFT" for t in drafts)
    assert client.get("/api/v1/tools/does-not-exist").status_code == 404


def test_registered_tool_covers_capability() -> None:
    """A REGISTERED tool must make the capability detector classify steps as covered."""
    tool = _register()
    client.post(f"/api/v1/tools/{tool['id']}/verify")
    client.post(f"/api/v1/tools/{tool['id']}/activate")

    response = client.post(
        "/api/v1/tasks",
        json={"goal": "use the calculator to add two numbers", "context": {}},
    )
    assert response.status_code == 201
    body = response.json()
    # Phase 6 reasoner has no executor yet: a covered plan completes with the
    # honest PLANNED placeholder result instead of a fabricated output.
    assert body["status"] == "COMPLETED"
    assert body["result"]["kind"] == "PLANNED"
    assert body["result"]["detail"] == "All steps are covered by registered tools; execution pipeline ships in Phase 7."


def test_events_for_lifecycle() -> None:
    tool = _register()
    client.post(f"/api/v1/tools/{tool['id']}/verify")
    client.post(f"/api/v1/tools/{tool['id']}/activate")
    types = [e["type"] for e in client.get("/api/v1/events", params={"limit": 50}).json()]
    assert "tool.verified" in types
    assert "tool.registered" in types
    verified = [e for e in client.get("/api/v1/events").json() if e["type"] == "tool.verified"][-1]
    assert verified["payload"]["scope"] == "structural"
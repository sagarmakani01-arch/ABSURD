"""Phase 9/10 tests: memory system, evaluation pipeline, evolution loop."""

from __future__ import annotations

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


def _register_and_activate() -> dict[str, object]:
    tool = client.post("/api/v1/tools", json=SAMPLE).json()
    client.post(f"/api/v1/tools/{tool['id']}/verify")
    client.post(f"/api/v1/tools/{tool['id']}/activate")
    return tool


def _submit(goal: str, context: dict[str, object]) -> dict[str, object]:
    return client.post(
        "/api/v1/tasks", json={"goal": goal, "context": context}
    ).json()


def test_failure_written_to_experience_memory() -> None:
    _submit("fetch weather data", {})
    rows = client.get("/api/v1/memory/experience", params={"outcome": "failure"}).json()
    assert rows
    top = rows[0]
    assert top["kind"] == "task"
    assert "missing capability" in top["lessons"][0]
    assert not any("unavailable" in lesson for lesson in top["lessons"])


def test_registration_adds_enables_edges() -> None:
    tool = _register_and_activate()
    edges = client.get("/api/v1/memory/graph", params={"relation": "enables"}).json()
    assert any(
        e["subject"] == f"tool:{tool['id']}" and e["target"] == "capability:arithmetic"
        for e in edges
    )


def test_gap_task_adds_requires_edges_and_coverage_query() -> None:
    task = _submit("parse html documents", {})
    edges = client.get("/api/v1/memory/graph", params={"relation": "requires"}).json()
    assert any(e["subject"] == f"task:{task['id']}" for e in edges)

    gaps = client.get("/api/v1/memory/graph/coverage-gaps").json()
    task_gaps = [g for g in gaps if g["task_id"] == task["id"]]
    assert task_gaps and not task_gaps[0]["covered"]

    # Registering a tool that provides the capability closes the gap.
    tool = client.post(
        "/api/v1/tools",
        json={**SAMPLE, "name": "html_parser", "capabilities": ["parse_html_documents"]},
    ).json()
    client.post(f"/api/v1/tools/{tool['id']}/verify")
    client.post(f"/api/v1/tools/{tool['id']}/activate")

    gaps = client.get("/api/v1/memory/graph/coverage-gaps").json()
    task_gaps = [g for g in gaps if g["task_id"] == task["id"]]
    assert task_gaps and task_gaps[0]["covered"] is True


def test_tool_memory_usage_empty_without_executions() -> None:
    _register_and_activate()
    assert client.get("/api/v1/memory/tools-usage").json() == {}


def test_structural_evaluation_reports_sandbox_unavailable() -> None:
    tool = client.post("/api/v1/tools", json=SAMPLE).json()
    result = client.post("/api/v1/evaluations", json={"tool_id": tool["id"]}).json()
    assert result["verification_score"] == 1.0
    assert result["behavioral"] == {
        "available": False,
        "reason": "Sandboxed test execution is not implemented yet; structural gate only.",
    }
    assert result["checks_passed"] == result["checks_total"] == 8

    broken = client.post(
        "/api/v1/tools", json={**SAMPLE, "source_code": "", "capabilities": []}
    ).json()
    result = client.post("/api/v1/evaluations", json={"tool_id": broken["id"]}).json()
    assert result["verification_score"] < 1.0
    failed = {c["name"] for c in result["checks"] if not c["passed"]}
    assert "field.source_code" in failed
    assert "field.capabilities" in failed


def test_evolution_metrics_reflect_activity() -> None:
    before = client.get("/api/v1/evolution/metrics").json()
    _register_and_activate()
    _submit("render a chart", {})
    after = client.get("/api/v1/evolution/metrics").json()
    assert after["tasks_total"] == before["tasks_total"] + 1
    assert after["tools_registered"] == before["tools_registered"] + 1
    assert after["failures_by_kind"].get("NO_CAPABILITY", 0) >= 1
    assert after["gap_edges"] >= 1
    assert after["executions"] == 0

    types = [e["type"] for e in client.get("/api/v1/evolution/events").json()]
    assert "failure.analyzed" in types


def test_quarantine_dormant_until_real_executions() -> None:
    _register_and_activate()
    quarantine = None
    for _ in range(5):
        # Surrogate consecutive failures are NOT injected; quarantine must
        # stay dormant since ExecutionRecord never has failures yet.
        ...
    metrics = client.get("/api/v1/evolution/metrics").json()
    assert metrics["tools_quarantined"] == 0
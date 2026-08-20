"""Phase 12 tests: deterministic tool generation (template strategy)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

GAP = {
    "name_hint": "parse_html_documents",
    "description": "parse html documents",
    "input_schema": {"html": "str"},
    "output_schema": {"headings": "list"},
}


def _submit(goal: str, expected_io: object | None = None) -> dict[str, object]:
    return client.post(
        "/api/v1/tasks",
        json={"goal": goal, "context": {"expected_io": expected_io} if expected_io else {}},
    ).json()


def test_template_candidate_is_draft_and_valid_python() -> None:
    tool = client.post("/api/v1/tools/generate", json=GAP).json()
    assert tool["status"] == "DRAFT"
    assert tool["name"] == "parse_html_documents"
    assert tool["capabilities"] == ["parse_html_documents"]
    assert tool["provenance"]["strategy"] == "template"
    compile(tool["source_code"], "<generated>", "exec")
    assert tool["tests"]


def test_generation_is_idempotent() -> None:
    first = client.post("/api/v1/tools/generate", json=GAP).json()
    again = client.post("/api/v1/tools/generate", json=GAP).json()
    assert again["id"] == first["id"]
    assert client.get("/api/v1/tools", params={"status": "DRAFT"}).json().__len__() == 1


def test_engine_auto_generates_candidates_for_gaps() -> None:
    head = client.get("/api/v1/evolution/metrics").json()["tools_generated"]
    task = _submit("parse html documents")
    assert task["status"] == "FAILED"

    tools = client.get("/api/v1/tools").json()
    assert any(t["name"] == "parse_html_documents" and t["status"] == "DRAFT" for t in tools)

    after = client.get("/api/v1/evolution/metrics").json()
    assert after["tools_generated"] >= head + 1
    assert after["generation_available"] is True
    assert after["generation_strategies"] == ["template"]

    types = [e["type"] for e in client.get("/api/v1/evolution/events").json()]
    assert "tool.generated" in types


def test_registering_generated_candidate_closes_the_loop() -> None:
    """gap -> auto-generated DRAFT -> verify -> activate -> task COMPLETED.

    With real sandbox execution (Phase 13b) the template candidate can only
    fulfill the step when its outputs are echoable from the inputs, so the
    loop closes with a normalize_text gap whose output key is an input key.
    """
    expected_io = [
        {"inputs": {"text": "str", "trimmed": "str"}, "outputs": {"trimmed": "str"}}
    ]
    task = client.post(
        "/api/v1/tasks",
        json={"goal": "normalize text", "context": {"expected_io": expected_io}},
    ).json()
    assert task["status"] == "FAILED"
    drafts = client.get("/api/v1/tools", params={"status": "DRAFT"}).json()
    candidate = next(t for t in drafts if t["name"] == "normalize_text")

    gaps = client.get("/api/v1/memory/graph/coverage-gaps").json()
    assert any(g["task_id"] == task["id"] and not g["covered"] for g in gaps)

    client.post(f"/api/v1/tools/{candidate['id']}/verify")
    registered = client.post(f"/api/v1/tools/{candidate['id']}/activate").json()
    assert registered["status"] == "REGISTERED"

    gaps = client.get("/api/v1/memory/graph/coverage-gaps").json()
    assert any(g["task_id"] == task["id"] and g["covered"] for g in gaps)

    rerun = client.post(
        "/api/v1/tasks",
        json={
            "goal": "normalize text",
            "context": {
                "expected_io": expected_io,
                "inputs": [{"text": "raw", "trimmed": "clean"}],
            },
        },
    ).json()
    assert rerun["status"] == "COMPLETED"
    assert rerun["error"] is None
    assert rerun["result"]["kind"] == "EXECUTED"
    assert rerun["result"]["outputs"][0]["output"] == {"trimmed": "clean"}
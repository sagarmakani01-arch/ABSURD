"""Phase 13d tests: LLM-assisted generation and revisions via a fake transport.

The real transport is never exercised in tests; an in-process subclass stands
in for the OpenAI-compatible API so the plumbing, contract validation, event
stream, and promotion path are tested deterministically. The service always
re-derives its transport from environment configuration (`llm_service.reset()`
from our conftest), so nothing here leaks into other tests.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.generator import sanitize_name
from app.services.llm import LLMError, LLMTransport, llm_service

client = TestClient(app)

GAP = {
    "name_hint": "uppercase_text",
    "description": "capitalize the text",
    "inputs": {"text": "str"},
    "outputs": {"upper": "str"},
}


class FakeLLMTransport(LLMTransport):
    """Deterministic in-process stand-in for the model API.

    Writes a real `inputs: dict -> dict` implementation for realizeable gap
    specs and refuses (with a structured error) what it cannot do. `revise_tool`
    returns the tool's own source plus a revision marker — simulated repair.
    """

    def __init__(self) -> None:
        super().__init__(base_url="fake://transport", api_token="fake", model="fake-model")

    def generate_tool(self, gap_spec) -> dict[str, object]:
        name = sanitize_name(gap_spec.name_hint or gap_spec.description or "tool")
        outputs = list(gap_spec.output_schema)
        source = None
        if "upper" in outputs and "text" in gap_spec.input_schema:
            source = (
                f"def {name}(inputs: dict) -> dict:\n"
                f"    return {{'upper': inputs['text'].upper()}}\n"
            )
        elif outputs and all(k in gap_spec.input_schema for k in outputs):
            source = (
                f"def {name}(inputs: dict) -> dict:\n"
                f"    return {{k: inputs[k] for k in {outputs!r} if k in inputs}}\n"
            )
        if source is None:
            raise LLMError("unsupported_goal", "fake transport cannot realize this gap spec")
        tests = [
            f"fn = {name}",
            "result = fn({})",
            "assert isinstance(result, dict)",
            f"assert set(result.keys()) <= set({list(gap_spec.output_schema)!r})",
        ]
        return self._validate_bundle(
            {"source_code": source, "tests": tests, "description": gap_spec.description}
        )

    def revise_tool(self, tool, feedback: list[str]) -> dict[str, object]:
        return self._validate_bundle(
            {
                "source_code": tool.source_code + "\n# revised by fake transport\n",
                "tests": list(tool.tests or []),
                "description": tool.description,
            }
        )


@pytest.fixture()
def fake_llm():
    llm_service.transport = FakeLLMTransport()
    yield
    llm_service.reset()


def _submit(goal: str, context: dict[str, object]) -> dict[str, object]:
    return client.post("/api/v1/tasks", json={"goal": goal, "context": context}).json()


def test_unavailable_without_transport() -> None:
    assert llm_service.available is False
    metrics = client.get("/api/v1/evolution/metrics").json()
    assert metrics["revision_available"] is False
    assert metrics["generation_strategies"] == ["template"]


def test_revision_still_fails_closed_without_transport() -> None:
    tool = client.post("/api/v1/tools", json={
        "name": "calculator",
        "description": "Arithmetic",
        "source_code": "def calculator(inputs: dict) -> dict:\n    return {'result': inputs['a'] + inputs['b']}\n",
        "capabilities": ["arithmetic"],
        "tests": ["fn = calculator", "result = fn({})", "assert isinstance(result, dict)"],
        "input_schema": {"a": "number", "b": "number"},
        "output_schema": {"result": "number"},
    }).json()
    client.post(f"/api/v1/tools/{tool['id']}/verify")
    client.post(f"/api/v1/tools/{tool['id']}/activate")
    resp = client.post("/api/v1/evolution/revisions", json={"tool_id": tool["id"]})
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "revision_generation_unavailable"


def test_generation_uses_llm_strategy_when_configured(fake_llm) -> None:
    task = _submit("uppercase the text", {"expected_io": [GAP]})
    assert task["status"] == "FAILED"

    metrics = client.get("/api/v1/evolution/metrics").json()
    assert metrics["revision_available"] is True
    assert metrics["generation_strategies"] == ["template", "llm"]

    drafts = client.get("/api/v1/tools", params={"status": "DRAFT"}).json()
    candidate = next(t for t in drafts if t["name"] == "uppercase_the_text")
    assert candidate["provenance"]["strategy"] == "llm"

    events = client.get("/api/v1/evolution/events").json()
    types = [e["type"] for e in events]
    assert "tool.generation_started" in types
    assert "tool.generated" in types


def test_llm_candidate_closes_the_loop(fake_llm) -> None:
    _submit("uppercase the text", {"expected_io": [GAP]})
    candidate = next(
        t for t in client.get("/api/v1/tools", params={"status": "DRAFT"}).json()
        if t["name"] == "uppercase_the_text"
    )
    client.post(f"/api/v1/tools/{candidate['id']}/verify")
    client.post(f"/api/v1/tools/{candidate['id']}/activate")

    rerun = _submit(
        "uppercase the text",
        {"expected_io": [GAP], "inputs": [{"text": "hello"}]},
    )
    assert rerun["status"] == "COMPLETED"
    assert rerun["result"]["outputs"][0]["output"] == {"upper": "HELLO"}


def test_llm_generation_falls_back_to_template_on_error(fake_llm) -> None:
    task = _submit("reverse the zodiac", {"expected_io": [{
        "inputs": {"sign": "str"},
        "outputs": {"reversed": "str"},
    }]})
    assert task["status"] == "FAILED"

    drafts = client.get("/api/v1/tools", params={"status": "DRAFT"}).json()
    candidate = next(t for t in drafts if t["name"] == "reverse_the_zodiac")
    # The fake refused this gap; generation fell back to the template strategy
    # with a visible error event on the stream.
    assert candidate["provenance"]["strategy"] == "template"

    events = client.get("/api/v1/evolution/events").json()
    requested = next(
        e for e in events
        if e["type"] == "tool.generation_requested" and e["payload"]["strategy"] == "llm"
    )
    assert requested["payload"]["error"] == "unsupported_goal"
    assert requested["payload"]["fallback"] is True


def test_revision_cycle_applies_improved_source_on_promotion(fake_llm) -> None:
    tool = client.post("/api/v1/tools", json={
        "name": "calculator",
        "description": "Arithmetic",
        "source_code": "def calculator(inputs: dict) -> dict:\n    return {'result': inputs['a'] + inputs['b']}\n",
        "capabilities": ["arithmetic"],
        "tests": ["fn = calculator", "result = fn({})", "assert isinstance(result, dict)"],
        "input_schema": {"a": "number", "b": "number"},
        "output_schema": {"result": "number"},
    }).json()
    client.post(f"/api/v1/tools/{tool['id']}/verify")
    client.post(f"/api/v1/tools/{tool['id']}/activate")

    revision = client.post("/api/v1/evolution/revisions", json={"tool_id": tool["id"]})
    assert revision.status_code == 200
    assert revision.json()["status"] == "improved"
    assert revision.json()["version"] == "0.1.1"

    events = client.get("/api/v1/evolution/events").json()
    assert any(e["type"] == "evolution.revision_improved" for e in events)

    promoted = client.post(
        "/api/v1/evolution/promotions",
        json={"tool_id": tool["id"], "version": "0.1.1"},
    ).json()
    assert promoted["status"] == "REGISTERED"

    updated = client.get(f"/api/v1/tools/{tool['id']}").json()
    assert updated["version"] == "0.1.1"
    assert updated["parent_version"] == "0.1.0"
    assert updated["source_code"].endswith("# revised by fake transport\n")

    # The revised tool still executes end-to-end.
    response = client.post(
        "/api/v1/tasks",
        json={"goal": "use the calculator to add numbers", "context": {"inputs": [{"a": 2, "b": 3}]}},
    ).json()
    assert response["status"] == "COMPLETED"
    assert response["result"]["outputs"][0]["output"] == {"result": 5}
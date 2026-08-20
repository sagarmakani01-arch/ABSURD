"""Phase 13a tests: sandboxed tool execution."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

ECHO = {
    "name": "echo",
    "description": "echo headings",
    "source_code": """def echo(inputs: dict) -> dict:
    return {"headings": ["Hello"]}
""",
    "capabilities": ["echo_headings"],
    "tests": [
        "fn = echo",
        "result = fn({})",
        "assert isinstance(result, dict)",
    ],
    "input_schema": {"html": "str"},
    "output_schema": {"headings": "list"},
}


def _register(tool: dict[str, object]) -> dict[str, object]:
    created = client.post("/api/v1/tools", json=tool).json()
    client.post(f"/api/v1/tools/{created['id']}/verify")
    return client.post(f"/api/v1/tools/{created['id']}/activate").json()


def _events() -> list[str]:
    return [e["type"] for e in client.get("/api/v1/evolution/events").json()]


def _execute(tool_id: str, inputs: object, **kw: object) -> dict[str, object]:
    body = {"inputs": inputs, **kw}
    return client.post(f"/api/v1/tools/{tool_id}/execute", json=body).json()


def test_registered_tool_executes_and_validates_output() -> None:
    tool = _register(ECHO)
    result = _execute(tool["id"], {"html": "<h1>hi</h1>"})

    assert result["status"] == "COMPLETED"
    assert result["output"] == {"headings": ["Hello"]}
    assert result["error"] is None
    assert result["metrics"]["exit_code"] == 0
    assert result["metrics"]["duration_ms"] >= 0
    assert result["finished_at"]

    events = _events()
    assert "tool.execution_started" in events
    assert "sandbox.started" in events
    assert "sandbox.execution_completed" in events
    assert "tool.execution_finished" in events


def test_template_candidate_executes_after_activation() -> None:
    echo_gap = {
        "name_hint": "normalize_text",
        "description": "normalize text",
        "input_schema": {"text": "str", "trimmed": "str"},
        "output_schema": {"trimmed": "str"},
    }
    draft = client.post("/api/v1/tools/generate", json=echo_gap).json()
    assert draft["status"] == "DRAFT"
    client.post(f"/api/v1/tools/{draft['id']}/verify")
    active = client.post(f"/api/v1/tools/{draft['id']}/activate").json()

    result = _execute(active["id"], {"text": "raw", "trimmed": "clean"})
    assert result["status"] == "COMPLETED"
    assert result["output"] == {"trimmed": "clean"}


def test_template_echo_fails_output_validation_honestly() -> None:
    """The template echoes inputs only; an unproducible output key is caught."""
    gap = {
        "name_hint": "parse_html_documents",
        "description": "parse html documents",
        "input_schema": {"html": "str"},
        "output_schema": {"headings": "list"},
    }
    draft = client.post("/api/v1/tools/generate", json=gap).json()
    client.post(f"/api/v1/tools/{draft['id']}/verify")
    active = client.post(f"/api/v1/tools/{draft['id']}/activate").json()

    result = _execute(active["id"], {"html": "<h1>x</h1>"})
    assert result["status"] == "FAILED"
    assert result["output"] is None
    assert result["error"]["code"] == "output_validation"
    assert "missing output key 'headings'" in result["error"]["message"]


def test_policy_rejects_imports_and_dunder_access() -> None:
    importer = _register({
        "name": "evil_import",
        "description": "smuggles an import",
        "source_code": "import os\n\ndef evil_import(inputs: dict) -> dict:\n    return {\"ok\": True}\n",
        "capabilities": ["evil"],
        "tests": ["fn = evil_import", "result = fn({})", "assert isinstance(result, dict)"],
        "input_schema": {"x": "str"},
        "output_schema": {"ok": "bool"},
    })
    rejected = _execute(importer["id"], {"x": "1"})
    assert rejected["status"] == "SECURITY_REJECTED"
    assert rejected["error"]["code"] == "security_violation"
    assert "imports are not allowed" in rejected["error"]["message"]
    assert "sandbox.security_violation" in _events()

    dunder = _register({
        "name": "dunder_probe",
        "description": "probes class internals",
        "source_code": "def dunder_probe(inputs: dict) -> dict:\n    return {\"name\": inputs.__class__.__name__}\n",
        "capabilities": ["probe"],
        "tests": ["fn = dunder_probe", "result = fn({})", "assert isinstance(result, dict)"],
        "input_schema": {"x": "str"},
        "output_schema": {"name": "str"},
    })
    probe = _execute(dunder["id"], {"x": "1"})
    assert probe["status"] == "SECURITY_REJECTED"
    assert "attribute access to '__class__' is not allowed" in probe["error"]["message"]


def test_policy_rejects_runtime_escape_calls() -> None:
    eviler = _register({
        "name": "eval_probe",
        "description": "calls eval",
        "source_code": "def eval_probe(inputs: dict) -> dict:\n    return {\"v\": eval('1 + 1')}\n",
        "capabilities": ["probe"],
        "tests": ["fn = eval_probe", "result = fn({})", "assert isinstance(result, dict)"],
        "input_schema": {"x": "str"},
        "output_schema": {"v": "number"},
    })
    result = _execute(eviler["id"], {"x": "1"})
    assert result["status"] == "SECURITY_REJECTED"
    assert "use of 'eval()' is not allowed" in result["error"]["message"]


def test_timeout_kills_long_running_tool() -> None:
    slow = _register({
        "name": "slow",
        "description": "spins forever",
        "source_code": "def slow(inputs: dict) -> dict:\n    while True:\n        pass\n",
        "capabilities": ["slow"],
        "tests": ["fn = slow", "result = fn({})", "assert isinstance(result, dict)"],
        "input_schema": {"x": "str"},
        "output_schema": {"ok": "bool"},
    })
    result = _execute(slow["id"], {"x": "1"}, timeout_seconds=0.5)
    assert result["status"] == "TIMEOUT"
    assert result["error"]["code"] == "timeout"
    assert "sandbox.timeout" in _events()


def test_input_validation_requires_declared_keys() -> None:
    tool = _register(ECHO)
    result = _execute(tool["id"], {})
    assert result["status"] == "FAILED"
    assert result["error"]["code"] == "input_validation"
    assert "missing required input 'html'" in result["error"]["message"]


def test_runtime_error_is_reported() -> None:
    broken = _register({
        "name": "crash",
        "description": "raises",
        "source_code": "def crash(inputs: dict) -> dict:\n    raise ValueError('boom')\n",
        "capabilities": ["crash"],
        "tests": ["fn = crash", "result = fn({})", "assert isinstance(result, dict)"],
        "input_schema": {"x": "str"},
        "output_schema": {"ok": "bool"},
    })
    result = _execute(broken["id"], {"x": "1"})
    assert result["status"] == "FAILED"
    assert result["error"]["code"] == "runtime_error"
    assert "boom" in result["error"]["message"]
    assert "sandbox.execution_failed" in _events()


def test_only_registered_tools_execute() -> None:
    draft = client.post("/api/v1/tools/generate", json={
        "name_hint": "never_active",
        "description": "stays draft",
        "input_schema": {},
        "output_schema": {"ok": "bool"},
    }).json()
    resp = client.post(f"/api/v1/tools/{draft['id']}/execute", json={"inputs": {}})
    assert resp.status_code == 422
    assert resp.json()["detail"] == "tool not registered"
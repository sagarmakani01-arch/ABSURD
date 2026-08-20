"""Phase 14 tests: composition matching — two tools chained by schema link.

The detector returns `covered` with `composed=True` and an ordered chain
[A, B] when A consumes the step's inputs and produces the types B requires,
and B produces the step's outputs. The engine then executes A, feeds A's
output into B, and records both executions.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

TOOL_A = {
    "name": "split_rows",
    "description": "Parses raw text into rows.",
    "source_code": (
        "def split_rows(inputs: dict) -> dict:\n"
        "    return {'rows': [inputs.get('text', '').split('|')]}\n"
    ),
    "input_schema": {"text": "str"},
    "output_schema": {"rows": "list"},
    "capabilities": ["split_rows"],
    "tests": ["fn = split_rows", "result = fn({'text': 'a|b'})", "assert isinstance(result, dict)"],
}

TOOL_B = {
    "name": "rows_to_markdown",
    "description": "Renders rows as a markdown table.",
    "source_code": (
        "def rows_to_markdown(inputs: dict) -> dict:\n"
        "    parts = ['| ' + ' | '.join(str(c) for c in row) + ' |' for row in inputs.get('rows', [])]\n"
        "    return {'markdown': chr(10).join(parts)}\n"
    ),
    "input_schema": {"rows": "list"},
    "output_schema": {"markdown": "str"},
    "capabilities": ["rows_to_markdown"],
    "tests": ["fn = rows_to_markdown", "result = fn({'rows': [['a', 'b']]})", "assert isinstance(result, dict)"],
}


def _register(body: dict) -> str:
    tool = client.post("/api/v1/tools", json=body).json()
    client.post(f"/api/v1/tools/{tool['id']}/verify")
    client.post(f"/api/v1/tools/{tool['id']}/activate")
    return tool["id"]


def test_detector_composes_two_tools() -> None:
    from app.core.agent.detector import CapabilityDetector, Coverage, RegistryTool
    from app.core.agent.planner import Planner

    detector = CapabilityDetector()
    plan = Planner().perform("convert the text into a markdown table")
    plan.steps[0].expected_inputs = {"text": "str"}
    plan.steps[0].expected_outputs = {"markdown": "str"}

    tools = [
        RegistryTool(
            id="a",
            name="split_rows",
            capabilities=["split_rows"],
            input_schema={"text": "str"},
            output_schema={"rows": "list"},
        ),
        RegistryTool(
            id="b",
            name="rows_to_markdown",
            capabilities=["rows_to_markdown"],
            input_schema={"rows": "list"},
            output_schema={"markdown": "str"},
        ),
    ]
    plan2 = detector.evaluate(plan, tools)
    entry = plan2.entries[0]
    assert entry.coverage is Coverage.COVERED
    assert entry.composed is True
    assert entry.matched_tool_ids == ["a", "b"]


def test_detector_no_chain_when_link_missing() -> None:
    from app.core.agent.detector import CapabilityDetector, Coverage, RegistryTool
    from app.core.agent.planner import Planner

    detector = CapabilityDetector()
    plan = Planner().perform("convert the text into a markdown table")
    plan.steps[0].expected_inputs = {"text": "str"}
    plan.steps[0].expected_outputs = {"markdown": "str"}

    tools = [
        RegistryTool(
            id="a",
            name="split_rows",
            capabilities=["split_rows"],
            input_schema={"text": "str"},
            output_schema={"rows": "list"},
        ),
        # B needs `rows` but A emits `cells` — no link.
        RegistryTool(
            id="b",
            name="rows_to_markdown",
            capabilities=["rows_to_markdown"],
            input_schema={"cells": "list"},
            output_schema={"markdown": "str"},
        ),
    ]
    entry = detector.evaluate(plan, tools).entries[0]
    assert entry.coverage is Coverage.PARTIAL


def test_engine_executes_chain_end_to_end() -> None:
    a_id = _register(TOOL_A)
    b_id = _register(TOOL_B)

    task = client.post(
        "/api/v1/tasks",
        json={
            "goal": "convert the text into a markdown table",
            "context": {
                "inputs": [{"text": "alpha|beta"}],
                "expected_io": [
                    {"inputs": {"text": "str"}, "outputs": {"markdown": "str"}}
                ],
            },
        },
    ).json()

    assert task["status"] == "COMPLETED"
    outputs = task["result"]["outputs"]
    tool_ids = [o["tool_id"] for o in outputs]
    assert tool_ids == [a_id, b_id]
    assert outputs[0]["output"] == {"rows": [["alpha", "beta"]]}
    assert outputs[1]["output"]["markdown"] == "| alpha | beta |"
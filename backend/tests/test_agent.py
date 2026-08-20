"""Agent core unit tests: planner decomposition, detector coverage, reasoner."""

from __future__ import annotations

from app.core.agent.detector import CapabilityDetector, Coverage, RegistryTool
from app.core.agent.planner import Planner
from app.core.agent.reasoner import Reasoner


def test_planner_splits_on_boundaries() -> None:
    plan = Planner().perform("fetch weather data and send an email", {})
    assert plan.strategy == "split"
    assert len(plan.steps) == 2
    assert plan.steps[0].description == "fetch weather data"


def test_planner_flat_for_single_unit() -> None:
    plan = Planner().perform("compute fibonacci of 10", {})
    assert plan.strategy == "flat"
    assert len(plan.steps) == 1
    assert plan.steps[0].confidence == 1.0


def test_detector_gap_when_registry_empty() -> None:
    plan = Planner().perform("render a chart", {})
    entries = CapabilityDetector().evaluate(plan, []).entries
    assert entries[0].coverage is Coverage.GAP
    assert entries[0].gap_spec.name_hint == "render_a_chart"


def test_detector_covers_by_tool_name() -> None:
    plan = Planner().perform("run the calculator on two numbers", {})
    tools = [RegistryTool(id="t1", name="calculator", capabilities=["arithmetic"])]
    entries = CapabilityDetector().evaluate(plan, tools).entries
    assert entries[0].coverage is Coverage.COVERED
    assert entries[0].matched_tool_ids == ["t1"]
    assert entries[0].gap_spec is None


def test_reasoner_verdicts_gap_as_no_capability() -> None:
    plan = Planner().perform("render a chart", {})
    capability_plan = CapabilityDetector().evaluate(plan, [])
    output = Reasoner().synthesize(plan, capability_plan)
    assert output.error["kind"] == "NO_CAPABILITY"
    assert output.confidence == 0.0
    assert output.task_result is None


def test_reasoner_verdicts_covered_plan() -> None:
    plan = Planner().perform("run the calculator on two numbers", {})
    tools = [RegistryTool(id="t1", name="calculator", capabilities=["arithmetic"])]
    capability_plan = CapabilityDetector().evaluate(plan, tools)
    output = Reasoner().synthesize(plan, capability_plan)
    assert output.error is None
    assert output.task_result["kind"] == "PLANNED"


def test_schema_match_full_coverage() -> None:
    plan = Planner().perform("compute the sum", {"expected_io": [{
        "inputs": {"a": "number", "b": "number"},
        "outputs": {"result": "number"},
    }]})
    tool = RegistryTool(
        id="calc",
        name="calculator",
        capabilities=["arithmetic"],
        input_schema={"a": "number", "b": "float"},
        output_schema={"result": "int"},
    )
    entry = CapabilityDetector().evaluate(plan, [tool]).entries[0]
    assert entry.coverage is Coverage.COVERED
    assert entry.matched_tool_ids == ["calc"]
    assert entry.confidence == 1.0


def test_schema_mismatch_is_partial() -> None:
    """Tool matches inputs but not outputs -> PARTIAL, generation still needed."""
    plan = Planner().perform("analyze csv data", {"expected_io": [{
        "inputs": {"path": "str"},
        "outputs": {"summary": "str"},
    }]})
    tool = RegistryTool(
        id="csv",
        name="csv_reader",
        capabilities=["parsing"],
        input_schema={"path": "str"},
        output_schema={"rows": "list"},
    )
    entry = CapabilityDetector().evaluate(plan, [tool]).entries[0]
    assert entry.coverage is Coverage.PARTIAL
    assert entry.confidence == 0.7


def test_schema_only_match_is_full_coverage() -> None:
    """Schema compatibility alone suffices in v1 — lexical is only the fallback."""
    plan = Planner().perform("divide two numbers", {"expected_io": [{
        "inputs": {"a": "number", "b": "number"},
        "outputs": {"quotient": "number"},
    }]})
    tool = RegistryTool(
        id="div",
        name="division_engine",
        capabilities=["math"],
        input_schema={"a": "number", "b": "number"},
        output_schema={"quotient": "number"},
    )
    entry = CapabilityDetector().evaluate(plan, [tool]).entries[0]
    assert entry.coverage is Coverage.COVERED


def test_type_groups_are_compatible() -> None:
    plan = Planner().perform("use the calculator to subtract", {"expected_io": [{
        "inputs": {"a": "integer", "b": "float"},
        "outputs": {"result": "number"},
    }]})
    tool = RegistryTool(
        id="calc",
        name="calculator",
        capabilities=["arithmetic"],
        input_schema={"a": "number", "b": "int"},
        output_schema={"result": "number"},
    )
    entry = CapabilityDetector().evaluate(plan, [tool]).entries[0]
    assert entry.coverage is Coverage.COVERED


def test_reasoner_verdicts_partial() -> None:
    plan = Planner().perform("analyze csv data", {"expected_io": [{
        "inputs": {"path": "str"},
        "outputs": {"summary": "str"},
    }]})
    tool = RegistryTool(
        id="csv",
        name="csv_reader",
        capabilities=["parsing"],
        input_schema={"path": "str"},
        output_schema={"rows": "list"},
    )
    capability_plan = CapabilityDetector().evaluate(plan, [tool])
    output = Reasoner().synthesize(plan, capability_plan, generation_available=False)
    assert output.error["kind"] == "PARTIAL_CAPABILITY"
    assert output.confidence == 0.7
    assert output.error["missing"] == ["analyze_csv_data"]
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
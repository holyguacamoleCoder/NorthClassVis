"""execution.compile_plan(GoalSpec)、execution.extract_tool_results。"""
import pytest

from agent.common.contracts import PlanStep
from agent.intent.schemas import GoalSpec
from agent.execution import compile_plan
from agent.execution import extract_tool_results


def test_compile_plan_returns_empty_when_needs_clarification():
    goal = GoalSpec(needs_clarification=True, subject=["class"], mode=["trend"])
    steps = compile_plan(goal)
    assert steps == []


def test_compile_plan_class_trend():
    goal = GoalSpec(subject=["class"], mode=["trend"])
    steps = compile_plan(goal)
    assert len(steps) >= 1
    assert all(isinstance(s, PlanStep) for s in steps)
    tools = [s.tool for s in steps]
    assert "query_class" in tools


def test_compile_plan_student_portrait_merges_params():
    goal = GoalSpec(subject=["student"], mode=["portrait"], student_ids=["s1"])
    steps = compile_plan(goal)
    assert len(steps) >= 1
    step = steps[0]
    assert step.tool == "query_student"
    assert step.params.get("mode") == "portrait"
    assert step.params.get("student_ids") == ["s1"]


def test_compile_plan_multi_subject_mode_expands():
    goal = GoalSpec(subject=["student", "class"], mode=["portrait", "trend"])
    steps = compile_plan(goal)
    tools = [s.tool for s in steps]
    assert "query_student" in tools
    assert "query_class" in tools


def test_extract_tool_results():
    raw = [
        {"tool": "query_class", "input": {"mode": "trend"}, "status": "ok", "summary": "ok", "evidence": [], "visual_hints": [], "duration_ms": 1, "coverage": {}, "quality": {}, "error": ""},
    ]
    out = extract_tool_results(raw)
    assert len(out) == 1
    assert out[0].tool == "query_class"
    assert out[0].params == {"mode": "trend"}
    assert out[0].status == "ok"

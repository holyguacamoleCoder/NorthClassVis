"""execution/compiler.py：compile_plan、compile_execution_plan_to_steps。"""

import pytest

from agent.execution import compile_execution_plan_to_steps
from agent.execution import compile_plan
from agent.execution.schemas import ExecutionBatch
from agent.execution.schemas import ExecutionPlan
from agent.intent.schemas import GoalSpec
from agent.plan.schemas import SubTask
from agent.plan.schemas import TaskGraph


class _NoLLMConfig:
    def is_available(self):
        return False


class _NoLLMClient:
    config = _NoLLMConfig()


@pytest.fixture(autouse=True)
def disable_tot_by_default(monkeypatch):
    monkeypatch.setattr("agent.plan.planner.get_default_llm_client", lambda: _NoLLMClient())


def test_compile_plan_sets_scope_to_individual_by_single_student():
    goal = GoalSpec(subject=["student"], mode=["portrait"], student_ids=["s1"])
    steps = compile_plan(goal)
    assert len(steps) >= 1
    assert goal.scope == "individual"


def test_compile_plan_sets_scope_to_selected_by_classes():
    goal = GoalSpec(subject=["class"], mode=["trend"], classes=["Part"])
    steps = compile_plan(goal)
    assert len(steps) >= 1
    assert goal.scope == "selected"


def test_compile_plan_returns_empty_when_needs_clarification():
    goal = GoalSpec(needs_clarification=True, subject=["class"], mode=["trend"])
    assert compile_plan(goal) == []


def test_compile_execution_plan_to_steps_flattens_batches_in_order():
    graph = TaskGraph()
    graph.add_task(
        SubTask(
            task_id="t0",
            name="q1",
            required_tools=["query_class"],
            tool_params={"mode": "trend"},
            reason="first",
        )
    )
    graph.add_task(
        SubTask(
            task_id="t1",
            name="q2",
            required_tools=["query_student"],
            tool_params={"mode": "portrait", "student_ids": ["s1"]},
            reason="second",
        )
    )
    plan = ExecutionPlan(
        task_graph=graph,
        batches=[
            ExecutionBatch(batch_id="0", task_ids=["t0"], parallel=False),
            ExecutionBatch(batch_id="1", task_ids=["t1"], parallel=False),
        ],
    )
    steps = compile_execution_plan_to_steps(plan)
    assert [s.tool for s in steps] == ["query_class", "query_student"]
    assert steps[0].params == {"mode": "trend"}
    assert steps[1].params["student_ids"] == ["s1"]
    assert [s.reason for s in steps] == ["first", "second"]


def test_compile_execution_plan_to_steps_skips_missing_or_invalid_tasks():
    graph = TaskGraph()
    graph.add_task(
        SubTask(
            task_id="t0",
            name="bad",
            required_tools=[],
            tool_params={},
            purpose="no-tools",
        )
    )
    plan = ExecutionPlan(
        task_graph=graph,
        batches=[ExecutionBatch(batch_id="0", task_ids=["t-missing", "t0"], parallel=True)],
    )
    steps = compile_execution_plan_to_steps(plan)
    assert steps == []

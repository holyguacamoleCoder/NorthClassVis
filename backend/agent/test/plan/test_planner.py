"""build_task_graph(goal)、SimpleRuleStrategy。"""
import pytest

from agent.intent.schemas import GoalSpec
from agent.plan import build_task_graph
from agent.plan import select_strategy
from agent.plan.schemas import TaskGraph
from agent.plan.strategies import SimpleRuleStrategy
from agent.plan.strategies import ToTStrategy


class _NoLLMConfig:
    def is_available(self):
        return False


class _NoLLMClient:
    config = _NoLLMConfig()


class _YesLLMConfig:
    def is_available(self):
        return True


class _YesLLMClient:
    config = _YesLLMConfig()


@pytest.fixture(autouse=True)
def disable_tot_by_default(monkeypatch):
    monkeypatch.setattr("agent.plan.planner.get_default_llm_client", lambda: _NoLLMClient())


def test_build_task_graph_empty_when_needs_clarification():
    goal = GoalSpec(needs_clarification=True, subject=["class"], mode=["trend"])
    graph = build_task_graph(goal)
    assert isinstance(graph, TaskGraph)
    assert len(graph.tasks) == 0


def test_build_task_graph_class_trend():
    goal = GoalSpec(subject=["class"], mode=["trend"])
    graph = build_task_graph(goal)
    assert len(graph.tasks) >= 1
    tools = []
    for t in graph.tasks.values():
        tools.extend(t.required_tools)
    assert "query_class" in tools


def test_build_task_graph_student_portrait():
    goal = GoalSpec(subject=["student"], mode=["portrait"], student_ids=["s1"])
    graph = build_task_graph(goal)
    assert len(graph.tasks) >= 1
    task = next(iter(graph.tasks.values()))
    assert task.tool_params.get("student_ids") == ["s1"]


def test_select_strategy_without_llm_uses_simple():
    strategy = select_strategy(GoalSpec(subject=["class"], mode=["trend"]))
    assert isinstance(strategy, SimpleRuleStrategy)


def test_select_strategy_with_llm_uses_tot_for_three_phases(monkeypatch):
    """三阶段目标且 LLM 可用时选 ToTStrategy；单阶段仍为 Simple。"""
    monkeypatch.setattr("agent.plan.planner.get_default_llm_client", lambda: _YesLLMClient())
    goal_tot = GoalSpec(
        sub_goals=[
            {"subject": ["class"], "mode": ["trend"]},
            {"subject": ["class"], "mode": ["cluster"]},
            {"subject": ["student"], "mode": ["portrait"]},
        ],
    )
    strategy = select_strategy(goal_tot)
    assert isinstance(strategy, ToTStrategy)
    goal_simple = GoalSpec(subject=["class"], mode=["trend"])
    strategy_simple = select_strategy(goal_simple)
    assert isinstance(strategy_simple, SimpleRuleStrategy)

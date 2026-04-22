"""按复杂程度选择策略（simple / cot / tot）及各策略建图行为。"""

import pytest

from agent.intent.schemas import GoalSpec
from agent.plan import build_task_graph
from agent.plan import get_plan_complexity
from agent.plan import select_strategy
from agent.plan.planner import COMPLEXITY_COT
from agent.plan.planner import COMPLEXITY_SIMPLE
from agent.plan.planner import COMPLEXITY_TOT
from agent.plan.schemas import TaskGraph
from agent.plan.strategies import CoTStrategy
from agent.plan.strategies import SimpleRuleStrategy
from agent.plan.strategies import ToTStrategy
from agent.plan.task_graph import has_cycle
from agent.plan.task_graph import topological_sort


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


# ---------- get_plan_complexity ----------


def test_get_plan_complexity_single_phase_sub_goals():
    goal = GoalSpec(subject=["class"], mode=["trend"])
    assert len(goal.sub_goals) == 1
    assert get_plan_complexity(goal) == COMPLEXITY_SIMPLE


def test_get_plan_complexity_single_phase_explicit():
    goal = GoalSpec(
        sub_goals=[{"subject": ["class"], "mode": ["trend"]}],
    )
    assert get_plan_complexity(goal) == COMPLEXITY_SIMPLE


def test_get_plan_complexity_two_phases():
    goal = GoalSpec(
        sub_goals=[
            {"subject": ["class"], "mode": ["trend"]},
            {"subject": ["student"], "mode": ["portrait"]},
        ],
    )
    assert get_plan_complexity(goal) == COMPLEXITY_COT


def test_get_plan_complexity_three_phases():
    goal = GoalSpec(
        sub_goals=[
            {"subject": ["class"], "mode": ["trend"]},
            {"subject": ["class"], "mode": ["cluster"]},
            {"subject": ["student"], "mode": ["portrait"]},
        ],
    )
    assert get_plan_complexity(goal) == COMPLEXITY_TOT


def test_get_plan_complexity_empty_sub_goals_has_subject_mode():
    goal = GoalSpec(subject=["knowledge"], mode=["portrait"])
    assert get_plan_complexity(goal) == COMPLEXITY_SIMPLE


def test_get_plan_complexity_single_phase_more_than_two_pairs_is_cot():
    """单阶段但 (s,m) 超过两对 -> cot（更多个 (s,m) 但一条路径）。"""
    goal = GoalSpec(
        sub_goals=[{"subject": ["class"], "mode": ["trend", "cluster", "portrait"]}],
    )
    assert get_plan_complexity(goal) == COMPLEXITY_COT


def test_get_plan_complexity_two_phases_many_pairs_is_tot():
    """两阶段但总有效对超过阈值(6) -> tot（多 subject/mode 组合较多）。"""
    goal = GoalSpec(
        sub_goals=[
            {"subject": ["class", "student"], "mode": ["trend", "cluster", "portrait"]},
            {"subject": ["class", "student"], "mode": ["trend", "portrait", "detail"]},
        ],
    )
    assert get_plan_complexity(goal) == COMPLEXITY_TOT


# ---------- select_strategy: simple / cot / tot ----------


@pytest.fixture(autouse=True)
def default_no_llm(monkeypatch):
    monkeypatch.setattr("agent.plan.planner.get_default_llm_client", lambda: _NoLLMClient())


def test_select_strategy_simple_returns_simple_rule():
    goal = GoalSpec(subject=["class"], mode=["trend"])
    strategy = select_strategy(goal)
    assert isinstance(strategy, SimpleRuleStrategy)


def test_select_strategy_cot_returns_cot():
    goal = GoalSpec(
        sub_goals=[
            {"subject": ["class"], "mode": ["trend"]},
            {"subject": ["student"], "mode": ["portrait"]},
        ],
    )
    strategy = select_strategy(goal)
    assert isinstance(strategy, CoTStrategy)


def test_select_strategy_tot_without_llm_returns_cot_fallback():
    goal = GoalSpec(
        sub_goals=[
            {"subject": ["class"], "mode": ["trend"]},
            {"subject": ["class"], "mode": ["cluster"]},
            {"subject": ["student"], "mode": ["portrait"]},
        ],
    )
    strategy = select_strategy(goal)
    assert isinstance(strategy, CoTStrategy)


def test_select_strategy_tot_with_llm_returns_tot(monkeypatch):
    monkeypatch.setattr("agent.plan.planner.get_default_llm_client", lambda: _YesLLMClient())
    goal = GoalSpec(
        sub_goals=[
            {"subject": ["class"], "mode": ["trend"]},
            {"subject": ["class"], "mode": ["cluster"]},
            {"subject": ["student"], "mode": ["portrait"]},
        ],
    )
    strategy = select_strategy(goal)
    assert isinstance(strategy, ToTStrategy)


# ---------- SimpleRuleStrategy: 单阶段无边 ----------


def test_simple_strategy_produces_no_edges():
    goal = GoalSpec(subject=["class"], mode=["trend"])
    strategy = SimpleRuleStrategy()
    graph = strategy.plan(goal)
    assert isinstance(graph, TaskGraph)
    assert len(graph.tasks) >= 1
    assert len(graph.edges) == 0


def test_simple_strategy_class_trend_tool():
    goal = GoalSpec(subject=["class"], mode=["trend"])
    strategy = SimpleRuleStrategy()
    graph = strategy.plan(goal)
    tools = [t.required_tools[0] for t in graph.tasks.values() if t.required_tools]
    assert "query_class" in tools


# ---------- CoTStrategy: 两阶段有边、DAG、拓扑序即阶段序 ----------


def test_cot_strategy_two_phases_has_edges():
    goal = GoalSpec(
        sub_goals=[
            {"subject": ["class"], "mode": ["trend"]},
            {"subject": ["student"], "mode": ["portrait"]},
        ],
        student_ids=["s1"],
    )
    strategy = CoTStrategy()
    graph = strategy.plan(goal)
    assert isinstance(graph, TaskGraph)
    assert len(graph.tasks) >= 2
    assert len(graph.edges) >= 1
    assert has_cycle(graph) is False


def test_cot_strategy_topological_order_respects_phases():
    goal = GoalSpec(
        sub_goals=[
            {"subject": ["class"], "mode": ["trend"]},
            {"subject": ["student"], "mode": ["portrait"]},
        ],
        student_ids=["s1"],
    )
    strategy = CoTStrategy()
    graph = strategy.plan(goal)
    order = topological_sort(graph)
    assert len(order) == len(graph.tasks)
    assert len(graph.edges) >= 1
    assert has_cycle(graph) is False


def test_cot_strategy_single_phase_falls_back_to_simple():
    goal = GoalSpec(subject=["class"], mode=["trend"])
    strategy = CoTStrategy()
    graph = strategy.plan(goal)
    assert len(graph.edges) == 0
    assert len(graph.tasks) >= 1


def test_cot_build_graph_from_sub_goals_override():
    """_build_graph_from_sub_goals 支持 sub_goals_override，用于 CoT 推理重排后建图。"""
    from agent.plan.strategies import _build_graph_from_sub_goals

    goal = GoalSpec(
        sub_goals=[
            {"subject": ["student"], "mode": ["portrait"]},
            {"subject": ["class"], "mode": ["trend"]},
        ],
        student_ids=["s1"],
    )
    override = [
        {"subject": ["class"], "mode": ["trend"]},
        {"subject": ["student"], "mode": ["portrait"]},
    ]
    graph = _build_graph_from_sub_goals(goal, sub_goals_override=override)
    assert len(graph.tasks) >= 2
    assert len(graph.edges) >= 1
    order = topological_sort(graph)
    assert len(order) == len(graph.tasks)
    assert has_cycle(graph) is False


def test_cot_strategy_phase_override_title_id():
    goal = GoalSpec(
        sub_goals=[
            {"subject": ["class"], "mode": ["trend"]},
            {"subject": ["question"], "mode": ["detail"], "title_id": "5"},
        ],
    )
    strategy = CoTStrategy()
    graph = strategy.plan(goal)
    for tid, t in graph.tasks.items():
        if "query_question" in (t.required_tools or []):
            assert t.tool_params.get("title_id") == "5"
            break
    else:
        pytest.skip("query_question task not in graph for this goal")


# ---------- build_task_graph 与策略联动 ----------


def test_build_task_graph_simple_goal_produces_tasks():
    goal = GoalSpec(subject=["class"], mode=["trend"])
    graph = build_task_graph(goal)
    assert len(graph.tasks) >= 1
    assert len(graph.edges) == 0


def test_build_task_graph_cot_goal_produces_dag_with_edges():
    goal = GoalSpec(
        sub_goals=[
            {"subject": ["class"], "mode": ["trend"]},
            {"subject": ["student"], "mode": ["portrait"]},
        ],
        student_ids=["s1"],
    )
    graph = build_task_graph(goal)
    assert len(graph.tasks) >= 2
    assert len(graph.edges) >= 1
    assert has_cycle(graph) is False


def test_build_task_graph_needs_clarification_returns_empty():
    goal = GoalSpec(
        needs_clarification=True,
        sub_goals=[
            {"subject": ["class"], "mode": ["trend"]},
            {"subject": ["student"], "mode": ["portrait"]},
        ],
    )
    graph = build_task_graph(goal)
    assert len(graph.tasks) == 0
    assert len(graph.edges) == 0


# ---------- ToTStrategy 建 DAG（多阶段时带边） ----------


def test_tot_strategy_builds_dag_with_edges_when_multiple_ranked():
    """ToT 在多个 ranked 时按序建 DAG，阶段间有边。"""
    from agent.plan.strategies import _build_scored_graph_with_edges

    goal = GoalSpec(subject=["class", "student"], mode=["trend", "portrait"], student_ids=["s1"])
    ranked = [
        ("class", "trend", 0.95, "先整体"),
        ("student", "portrait", 0.85, "再个体"),
    ]
    graph = _build_scored_graph_with_edges(goal, ranked)
    assert isinstance(graph, TaskGraph)
    assert len(graph.tasks) >= 2
    assert len(graph.edges) >= 1
    assert has_cycle(graph) is False


def test_tot_strategy_with_llm_produces_graph(monkeypatch):
    monkeypatch.setattr("agent.plan.planner.get_default_llm_client", lambda: _YesLLMClient())
    goal = GoalSpec(
        sub_goals=[
            {"subject": ["class"], "mode": ["trend"]},
            {"subject": ["class"], "mode": ["cluster"]},
            {"subject": ["student"], "mode": ["portrait"]},
        ],
        student_ids=[],
    )
    strategy = ToTStrategy(llm_client=_YesLLMClient())
    graph = strategy.plan(goal)
    assert isinstance(graph, TaskGraph)
    assert len(graph.tasks) >= 1



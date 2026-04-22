"""CoT / ToT 策略使用真实 LLM 的测试（链式推理、分支打分）。不 mock 客户端，LLM 不可用时跳过。

运行并查看打印的任务图：pytest backend/agent/test/plan/test_plan_strategy_llm.py -v -m llm -s
"""

import pytest

from agent.common.llm_client import get_default_llm_client
from agent.intent.schemas import GoalSpec
from agent.plan import build_task_graph
from agent.plan.schemas import TaskGraph
from agent.plan.strategies import CoTStrategy
from agent.plan.strategies import ToTStrategy
from agent.plan.task_graph import has_cycle


def _print_task_graph(graph: TaskGraph, title: str = "任务图") -> None:
    """打印任务图便于观察：节点列表、依赖边、简要拓扑。运行 pytest 时需加 -s 才能看到输出。"""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)
    if not graph.tasks:
        print("  (无任务)")
        print("=" * 60 + "\n")
        return
    print("\n  [节点]")
    for tid, t in sorted(graph.tasks.items(), key=lambda x: x[0]):
        deps = ",".join(t.dependencies) if t.dependencies else "-"
        reason_short = (t.reason or "")[:50] + ("..." if len(t.reason or "") > 50 else "")
        print(f"    {tid}: name={t.name}  deps=[{deps}]  priority={t.priority}")
        print(f"         purpose={t.purpose}")
        if reason_short:
            print(f"         reason={reason_short}")
    print("\n  [边] (from -> to)")
    for a, b in graph.edges:
        print(f"    {a} -> {b}")
    # 拓扑序简要示意
    try:
        from agent.plan.task_graph import topological_sort
        order = topological_sort(graph)
        print("\n  [拓扑序] " + " -> ".join(order))
    except Exception:
        pass
    print("=" * 60 + "\n")


def _print_tot_debug(strategy: ToTStrategy) -> None:
    """打印 ToT 多方案评选详情（候选路径、各方案评分、最终选中）。"""
    debug = strategy.get_last_tot_debug() if hasattr(strategy, "get_last_tot_debug") else {}
    if not debug:
        print("  [ToT 调试] 无多方案评分信息（可能未走路径评选分支）")
        return
    print("\n  [ToT 候选路径]")
    plan_candidates = debug.get("plan_candidates") or {}
    for plan_id, path in sorted(plan_candidates.items(), key=lambda x: x[0]):
        path_str = " -> ".join([f"{s}/{m}" for s, m in path]) if path else "-"
        print(f"    {plan_id}: {path_str}")

    selected = debug.get("selected_plans") or []
    if selected:
        print("\n  [ToT 方案评分]")
        for item in selected:
            plan_id = item.get("plan_id")
            score = item.get("score")
            reason = str(item.get("reason") or "")
            reason_short = reason[:60] + ("..." if len(reason) > 60 else "")
            print(f"    {plan_id}: score={score:.2f} reason={reason_short}")

    chosen_plan = debug.get("chosen_plan")
    if chosen_plan:
        print(
            f"\n  [ToT 最终选择] {chosen_plan} "
            f"score={debug.get('chosen_score', 0.0):.2f}"
        )
        chosen_path = debug.get("chosen_path") or []
        chosen_str = " -> ".join([f"{s}/{m}" for s, m in chosen_path]) if chosen_path else "-"
        print(f"    path: {chosen_str}")


def _llm_available():
    try:
        client = get_default_llm_client()
        return client and getattr(client, "config", None) and client.config.is_available()
    except Exception:
        return False


@pytest.mark.llm
@pytest.mark.skipif(not _llm_available(), reason="LLM 未配置或不可用，跳过策略真实 LLM 测试")
class TestPlanStrategyRealLLM:
    """CoT / ToT 策略使用真实 LLM：链式推理与分支打分，仅当 LLM 可用时运行。"""

    def test_cot_strategy_llm_reason_and_build_dag(self):
        """CoT：两阶段目标，LLM 做链式推理（顺序理由 + ordered_phases）后建 DAG。"""
        goal = GoalSpec(
            sub_goals=[
                {"subject": ["class"], "mode": ["trend"]},
                {"subject": ["student"], "mode": ["portrait"]},
            ],
            student_ids=["s1"],
        )
        strategy = CoTStrategy(llm_client=get_default_llm_client())
        graph = strategy.plan(goal)
        _print_task_graph(graph, "CoT 建图结果（两阶段）")
        assert isinstance(graph, TaskGraph)
        assert len(graph.tasks) >= 2
        assert len(graph.edges) >= 1
        assert has_cycle(graph) is False

    def test_tot_strategy_llm_rank_and_build_dag(self):
        """ToT：多阶段目标，先生成多候选路径，再由 LLM 评选最优方案并建 DAG。"""
        goal = GoalSpec(
            sub_goals=[
                {"subject": ["class"], "mode": ["trend"]},
                {"subject": ["class"], "mode": ["cluster"]},
                {"subject": ["question"], "mode": ["detail"], "title_id": "3"},
                {"subject": ["student"], "mode": ["portrait"]},
            ],
            student_ids=["s1"],
        )
        strategy = ToTStrategy(llm_client=get_default_llm_client())
        graph = strategy.plan(goal)
        _print_task_graph(graph, "ToT 建图结果（多方案评选）")
        _print_tot_debug(strategy)
        assert isinstance(graph, TaskGraph)
        assert len(graph.tasks) >= 1
        assert has_cycle(graph) is False
        if len(graph.tasks) >= 2:
            assert len(graph.edges) >= 1

    def test_build_task_graph_cot_complexity_uses_llm(self):
        """通过 build_task_graph 走 cot 分支，使用真实 LLM 建图。"""
        goal = GoalSpec(
            sub_goals=[
                {"subject": ["class"], "mode": ["trend"]},
                {"subject": ["student"], "mode": ["portrait"]},
            ],
            student_ids=["s1"],
        )
        graph = build_task_graph(goal)
        _print_task_graph(graph, "build_task_graph(CoT) 建图结果")
        assert isinstance(graph, TaskGraph)
        assert len(graph.tasks) >= 2
        assert len(graph.edges) >= 1

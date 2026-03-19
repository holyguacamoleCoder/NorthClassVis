# 规划入口：根据目标复杂度选择策略（simple / cot / tot），生成任务图。

from typing import Any, Dict, List, Literal, Set, Tuple

from agent.common.log_config import ensure_agent_logger
from agent.common.llm_client import get_default_llm_client
from agent.intent.schemas import GoalSpec
from agent.plan.schemas import TaskGraph
from agent.plan.strategies import INTENT_PLAN_MAP
from agent.plan.strategies import CoTStrategy
from agent.plan.strategies import SimpleRuleStrategy
from agent.plan.strategies import ToTStrategy

_agent_logger = ensure_agent_logger()

COMPLEXITY_SIMPLE: Literal["simple"] = "simple"
COMPLEXITY_COT: Literal["cot"] = "cot"
COMPLEXITY_TOT: Literal["tot"] = "tot"

# 多 subject/mode 组合较多时的阈值：有效 (s,m) 对超过此数视为 tot
_TOT_PAIRS_THRESHOLD = 6
# 单阶段内最多一两对 (s,m) 才算 simple
_SIMPLE_MAX_PAIRS_IN_PHASE = 2


def _effective_pairs_in_phase(phase: Dict[str, Any], goal: GoalSpec) -> Set[Tuple[str, str]]:
    """阶段内在 INTENT_PLAN_MAP 中存在的 (subject, mode) 对集合。"""
    subjects = phase.get("subject") or goal.subject or ["class"]
    modes = phase.get("mode") or goal.mode or ["portrait"]
    if not isinstance(subjects, list):
        subjects = [subjects]
    if not isinstance(modes, list):
        modes = [modes]
    out: Set[Tuple[str, str]] = set()
    for s in subjects:
        for m in modes:
            if (s, m) in INTENT_PLAN_MAP:
                out.add((s, m))
    return out


def _count_effective_pairs_and_phases(goal: GoalSpec) -> Tuple[int, int, List[Set[Tuple[str, str]]]]:
    """
    返回 (总有效对数, 阶段数, 每阶段有效对集合列表)。
    无 sub_goals 但有 subject/mode 时视为单阶段。
    """
    sub_goals = goal.sub_goals or []
    if not sub_goals and (goal.subject or goal.mode):
        phase = {"subject": goal.subject or ["class"], "mode": goal.mode or ["portrait"]}
        per_phase = [_effective_pairs_in_phase(phase, goal)]
    else:
        per_phase = [_effective_pairs_in_phase(p, goal) for p in sub_goals]
    total_pairs = sum(len(s) for s in per_phase)
    n_phases = len(per_phase)
    return total_pairs, n_phases, per_phase


def get_plan_complexity(goal: GoalSpec) -> Literal["simple", "cot", "tot"]:
    """
    按 sub_goals 阶段数与阶段内 (s,m) 对数判定规划复杂度。

    - simple: len(sub_goals) <= 1 且阶段内等价只有一两对 (s,m)（subject/mode 各一或二且来自同一阶段）。
    - cot: len(sub_goals) == 2，或更多 (s,m) 但语义上一条路径（例如 class→student），不需多顺序比较。
    - tot: len(sub_goals) >= 3，或多 subject/mode 组合较多、需多种顺序/多种实现再选优。
    """
    total_pairs, n_phases, per_phase = _count_effective_pairs_and_phases(goal)

    if n_phases <= 1:
        pairs_in_phase = len(per_phase[0]) if per_phase else 0
        if pairs_in_phase <= _SIMPLE_MAX_PAIRS_IN_PHASE:
            return COMPLEXITY_SIMPLE
        return COMPLEXITY_COT

    if n_phases >= 3:
        return COMPLEXITY_TOT

    if total_pairs > _TOT_PAIRS_THRESHOLD:
        return COMPLEXITY_TOT

    return COMPLEXITY_COT


def select_strategy(goal: GoalSpec):
    """按目标复杂度选择规划策略：simple -> SimpleRuleStrategy，cot -> CoTStrategy，tot -> ToTStrategy（需 LLM，否则退化为 CoT/Simple）。"""
    client = get_default_llm_client()
    llm_available = bool(client and getattr(client, "config", None) and client.config.is_available())
    complexity = get_plan_complexity(goal)

    if complexity == COMPLEXITY_SIMPLE:
        strategy = SimpleRuleStrategy()
        _agent_logger.info(
            "Plan select_strategy: simple -> SimpleRuleStrategy (subject=%s mode=%s)",
            goal.subject,
            goal.mode,
        )
        return strategy

    if complexity == COMPLEXITY_COT:
        strategy = CoTStrategy(llm_client=client)
        _agent_logger.info(
            "Plan select_strategy: cot -> CoTStrategy (sub_goals=%d)",
            len(goal.sub_goals or []),
        )
        return strategy

    if complexity == COMPLEXITY_TOT:
        if llm_available:
            strategy = ToTStrategy(llm_client=client)
            _agent_logger.info(
                "Plan select_strategy: tot -> ToTStrategy (subject=%s mode=%s confidence=%.2f)",
                goal.subject,
                goal.mode,
                float(goal.confidence or 0.0),
            )
            return strategy
        strategy = CoTStrategy(llm_client=client)
        _agent_logger.info(
            "Plan select_strategy: tot 但 LLM 不可用 -> 降级 CoTStrategy (sub_goals=%d)",
            len(goal.sub_goals or []),
        )
        return strategy

    strategy = SimpleRuleStrategy()
    _agent_logger.info("Plan select_strategy: 默认 SimpleRuleStrategy (subject=%s mode=%s)", goal.subject, goal.mode)
    return strategy


def build_task_graph(goal: GoalSpec) -> TaskGraph:
    """将 GoalSpec 拆解为任务依赖图。"""
    if goal.needs_clarification:
        _agent_logger.info("Plan build_task_graph: 跳过，needs_clarification=True")
        return TaskGraph()
    strategy = select_strategy(goal)
    graph = strategy.plan(goal)
    n = len(graph.tasks)
    _agent_logger.info("Plan build_task_graph: 完成，任务数=%d task_ids=%s", n, list(graph.tasks.keys()))
    return graph

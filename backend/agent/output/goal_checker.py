from typing import List, Tuple

from agent.execution.schemas import TaskExecutionRecord
from agent.intent.schemas import GoalSpec
from agent.output.schemas import GoalCheckResult
from agent.common.contracts import ToolResult


def _normalize_subject_mode(goal: GoalSpec) -> List[Tuple[str, str]]:
    pairs: List[Tuple[str, str]] = []
    if goal.sub_goals:
        for sg in goal.sub_goals:
            s = sg.get("subject") or []
            m = sg.get("mode") or []
            s_val = (s[0] if isinstance(s, list) and s else s) or ""
            m_val = (m[0] if isinstance(m, list) and m else m) or ""
            if s_val or m_val:
                pairs.append((str(s_val), str(m_val)))
    else:
        s = goal.subject or []
        m = goal.mode or []
        s_val = (s[0] if isinstance(s, list) and s else s) or ""
        m_val = (m[0] if isinstance(m, list) and m else m) or ""
        if s_val or m_val:
            pairs.append((str(s_val), str(m_val)))
    return pairs


def _is_effective_result(record: TaskExecutionRecord, result: ToolResult) -> bool:
    """与 answer_generator 对齐：仅当 coverage.covered is True 视为有效，否则视为数据不足/未覆盖。"""
    if (record.status or "").lower() != "ok":
        return False
    if record.verification_passed is False:
        return False
    cov = result.coverage or {}
    if cov.get("covered") is not True:
        return False
    return True


def _match_pair_to_tool(pair: Tuple[str, str], tr: ToolResult) -> bool:
    s, m = pair
    tool = tr.tool or ""
    params = tr.params or {}
    mode = params.get("mode") or ""
    key = f"{s}/{m}"
    if "class" in s and "trend" in m and tool == "query_class" and mode == "trend":
        return True
    if "student" in s and "portrait" in m and tool == "query_student" and mode == "portrait":
        return True
    if "question" in s and tool == "query_question":
        return True
    return False


def check_goal_completion(
    goal: GoalSpec,
    execution_records: List[TaskExecutionRecord],
    tool_results: List[ToolResult],
) -> GoalCheckResult:
    """
    规则版目标达成校验：
    - 把 status/verification/coverage 都通过的 ToolResult 视为有效结果；
    - 对于每个 subject/mode（或 sub_goal），至少命中一条有效结果则视为该子目标完成；
    - 若所有必需子目标都完成，则 is_satisfied=True, can_stop_early=True。
    """
    if not execution_records or not tool_results:
        return GoalCheckResult(
            is_satisfied=False,
            can_stop_early=False,
            reason="尚无可用工具结果",
            confidence=0.0,
        )
    pairs = _normalize_subject_mode(goal)
    if not pairs:
        return GoalCheckResult(
            is_satisfied=True,
            can_stop_early=True,
            reason="无明确 subject/mode 约束，默认视为已满足。",
            confidence=0.3,
        )

    effective: List[Tuple[int, TaskExecutionRecord, ToolResult]] = []
    for idx, (rec, tr) in enumerate(zip(execution_records, tool_results)):
        if _is_effective_result(rec, tr):
            effective.append((idx, rec, tr))

    satisfied_pairs: List[Tuple[str, str]] = []
    supporting_task_ids: List[str] = []
    for pair in pairs:
        for _, rec, tr in effective:
            if _match_pair_to_tool(pair, tr):
                satisfied_pairs.append(pair)
                supporting_task_ids.append(rec.task_id)
                break

    missing = []
    for pair in pairs:
        if pair not in satisfied_pairs:
            missing.append(f"{pair[0]}/{pair[1]}")

    if not missing:
        return GoalCheckResult(
            is_satisfied=True,
            can_stop_early=True,
            reason="所有关键子目标均已有有效结果支撑。",
            missing_requirements=[],
            supporting_task_ids=supporting_task_ids,
            confidence=0.8,
        )

    return GoalCheckResult(
        is_satisfied=False,
        can_stop_early=False,
        reason="仍有子目标未被有效结果覆盖。",
        missing_requirements=missing,
        supporting_task_ids=supporting_task_ids,
        confidence=0.4,
    )


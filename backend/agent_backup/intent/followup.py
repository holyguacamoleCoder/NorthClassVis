import re
from typing import Optional

from agent.common.log_config import ensure_agent_logger
from agent.intent.clarifier import apply_clarification
from agent.intent.schemas import GoalSpec

_agent_logger = ensure_agent_logger()

_KNOWLEDGE_TOKENS = ["链表", "递归", "树", "图", "哈希", "排序", "动态规划"]


def _is_default_goal(goal: GoalSpec) -> bool:
    return (
        (goal.intent_type or "overview") == "overview"
        and (goal.subject or []) == ["class"]
        and (goal.mode or []) == ["portrait"]
        and not (goal.student_ids or [])
        and not (goal.knowledge or "").strip()
    )


# 带标签的学生编号前缀，其后整段按分隔符拆，不按正则碎片匹配
_STUDENT_ID_LABELS = ("学生编号", "学号", "student_id", "student_ids", "学生id", "学生ID")


def _extract_student_ids(text: str):
    q = (text or "").strip()
    if not q:
        return []
    # 1) 带标签的整段提取：取冒号/等号后的内容，只按显式分隔符拆
    for label in _STUDENT_ID_LABELS:
        if label in q:
            idx = q.find(label)
            rest = q[idx + len(label) :].strip()
            rest = re.sub(r"^[：:=\s]+", "", rest)
            if not rest:
                continue
            parts = re.split(r"[,，\s、]+", rest)
            out = [p.strip() for p in parts if (p and len(p.strip()) >= 4)]
            if out:
                return out
    # 2) 通用正则：保留原有模式，并增加长字母数字串（单条学号不被拆）
    candidates = re.findall(r"[A-Za-z0-9_-]{8,}|[A-Za-z]+[-_]?\d+|\b\d{4,}\b", q)
    seen = set()
    result = []
    for c in candidates:
        c = c.strip()
        if not c or c in seen:
            continue
        seen.add(c)
        result.append(c)
    return result


def _extract_knowledge(text: str) -> Optional[str]:
    q = (text or "").strip()
    if not q:
        return None
    for k in _KNOWLEDGE_TOKENS:
        if k in q:
            return k
    m = re.search(r"([\u4e00-\u9fa5A-Za-z0-9_+-]{2,20})知识点", q)
    if m:
        return (m.group(1) or "").strip() or None
    return None


def _goal_from_pending(pending_goal: dict) -> GoalSpec:
    g = GoalSpec()
    for k, v in (pending_goal or {}).items():
        if hasattr(g, k):
            setattr(g, k, v)
    return g


def merge_followup_goal(parsed_goal: GoalSpec, question: str, context: Optional[dict]) -> GoalSpec:
    """
    若上轮处于追问状态，将本轮回答补全到 pending_goal 上；
    无 pending 时直接返回 parsed_goal。
    """
    ctx = context or {}
    pending_goal = ctx.get("pending_goal")
    pending_needs_clarification = bool(ctx.get("pending_needs_clarification"))
    if not (pending_goal and pending_needs_clarification):
        return parsed_goal

    merged = _goal_from_pending(pending_goal)
    q = (question or "").strip()
    ids = _extract_student_ids(q)
    knowledge = _extract_knowledge(q)

    # 1) 用户本轮上下文优先
    if parsed_goal.student_ids:
        merged.student_ids = list(parsed_goal.student_ids)
    elif ids:
        merged.student_ids = ids

    if parsed_goal.knowledge:
        merged.knowledge = parsed_goal.knowledge
    elif knowledge:
        merged.knowledge = knowledge

    if parsed_goal.title_id:
        merged.title_id = parsed_goal.title_id
    if parsed_goal.time_window:
        merged.time_window = parsed_goal.time_window

    # 2) 若本轮解析并非默认兜底，可继承其意图轴
    if not _is_default_goal(parsed_goal):
        merged.intent_type = parsed_goal.intent_type
        merged.subject = list(parsed_goal.subject or merged.subject)
        merged.mode = list(parsed_goal.mode or merged.mode)
        merged.metric = parsed_goal.metric or merged.metric
        merged.is_out_of_domain = bool(parsed_goal.is_out_of_domain)

    # 3) 保留上下文槽位
    if parsed_goal.classes:
        merged.classes = list(parsed_goal.classes)
    if parsed_goal.majors:
        merged.majors = list(parsed_goal.majors)

    # 4) 重新应用澄清逻辑
    merged.needs_clarification = False
    merged.clarification_question = ""
    apply_clarification(merged)

    _agent_logger.info(
        "Intent merge_followup_goal: 合并 pending_goal，before_needs_clarification=%s after_needs_clarification=%s subject=%s mode=%s student_ids=%s knowledge=%s",
        pending_needs_clarification,
        merged.needs_clarification,
        merged.subject,
        merged.mode,
        merged.student_ids,
        merged.knowledge,
    )
    return merged

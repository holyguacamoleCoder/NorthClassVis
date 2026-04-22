# 追问模块：目标不清晰或缺少关键信息时，设置追问状态与问题文案。
# 以 LLM 为主：LLM 可通过 needs_clarification + clarification_question 主动触发并定制文案；
# 规则兜底：缺 knowledge/student/scope 时也触发，文案优先用 LLM 的，缺省时用下方常量。

from agent.intent.schemas import GoalSpec

STUDENT_CLARIFICATION = "您想分析哪些学生？请在界面框选学生后再提问，或直接说出学生编号。"
KNOWLEDGE_CLARIFICATION = "请问您想了解哪个知识点？（如：链表、递归、排序等）"
QUESTION_DETAIL_CLARIFICATION = "请提供要分析的题目编号（title_id），我再给出该题目的详细时间线和分布。"


def needs_clarification(goal: GoalSpec) -> bool:
    """判断是否应触发追问。LLM 设 goal.needs_clarification 即触发；规则仅对缺 knowledge/缺学生主体 触发，不因 scope=selected 单独追问。"""
    if goal.needs_clarification:
        return True
    subjects = goal.subject if isinstance(goal.subject, list) else [goal.subject] if goal.subject else []
    modes = goal.mode if isinstance(goal.mode, list) else [goal.mode] if goal.mode else []
    if "knowledge" in subjects and not goal.knowledge:
        return True
    if "student" in subjects and not (goal.student_ids or []):
        return True
    if "question" in subjects and "detail" in modes and not (goal.title_id and str(goal.title_id).strip()):
        return True
    return False


def build_clarification_question(goal: GoalSpec) -> str:
    """生成追问文案。优先使用 LLM 填写的 clarification_question；缺省时再按规则生成（知识点/学生）。"""
    if (goal.clarification_question or "").strip():
        return (goal.clarification_question or "").strip()
    subjects = goal.subject if isinstance(goal.subject, list) else [goal.subject] if goal.subject else []
    modes = goal.mode if isinstance(goal.mode, list) else [goal.mode] if goal.mode else []
    if "knowledge" in subjects and not goal.knowledge:
        return KNOWLEDGE_CLARIFICATION
    if "student" in subjects and not (goal.student_ids or []):
        return STUDENT_CLARIFICATION
    if "question" in subjects and "detail" in modes and not (goal.title_id and str(goal.title_id).strip()):
        return QUESTION_DETAIL_CLARIFICATION
    return ""


def apply_clarification(goal: GoalSpec) -> None:
    """
    根据当前 goal 状态补全 needs_clarification 与 clarification_question（原地修改）。
    编排层在 compile_plan 前调用，统一走追问逻辑。
    """
    if not needs_clarification(goal):
        return
    q = build_clarification_question(goal)
    if q:
        goal.needs_clarification = True
        goal.clarification_question = q

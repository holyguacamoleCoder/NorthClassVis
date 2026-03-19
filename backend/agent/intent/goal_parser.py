# 目标解析：用户 query → GoalSpec（LLM 主路径 + 规则兜底）。

import logging

from agent.common import extract_first_json_object
from agent.common.context_utils import normalize_context
from agent.common.llm_client import LLMClient
from agent.common.llm_client import get_default_llm_client
from agent.common.log_config import ensure_agent_logger
from agent.common.prompts import get_intent_few_shots
from agent.common.prompts import get_intent_parse_system_prompt

from agent.intent.schemas import GoalSpec

_agent_logger = ensure_agent_logger()

VALID_SUBJECTS = {"student", "question", "knowledge", "class"}
VALID_MODES = {"trend", "portrait", "cluster", "detail"}

INTENT_MATCHERS = [
    (["周", "每周", "趋势", "最近", "两周", "week"], "trend", "weekly_score", "recent_2w"),
    (["知识点", "链表", "递归", "树", "图"], "knowledge", "knowledge_score", ""),
    (["学生", "个体", "画像", "诊断"], "student", "student_profile", ""),
    (["提交", "提交记录", "attempt"], "submission", "submission_count", ""),
    (["聚类", "cluster", "群体"], "cluster", "cluster_distribution", ""),
]
KNOWLEDGE_TOKENS = ["链表", "递归", "树", "图", "哈希", "排序", "动态规划"]
STUDENT_CLARIFICATION = "你希望分析哪些学生？请提供 student_ids 或先在界面框选学生。"
MAX_TOKENS = 1024

def _derive_scope(goal: GoalSpec) -> str:
    """根据 student_ids / title_id 推导 scope；classes/majors 仅作筛选上下文，不强制 selected。"""
    ids = goal.student_ids or []
    if len(ids) == 1 or (goal.title_id and str(goal.title_id).strip()):
        return "individual"
    if len(ids) > 1:
        return "selected"
    return "all"


# 明显非学情关键词：命中且无学情关键词时强制 is_out_of_domain
_OOD_KEYWORDS = ("天气", "下雨", "气温", "股票", "基金", "做饭", "菜谱", "旅游", "新闻", "电影", "音乐")
_LEARNING_KEYWORDS = ("学生", "班级", "题目", "知识点", "成绩", "趋势", "作答", "提交", "画像", "聚类", "学情", "掌握", "答题")


def _rule_detect_out_of_domain(question: str) -> bool:
    """规则兜底：问题明显与学情无关时返回 True，供解析后覆盖 LLM 的 is_out_of_domain。"""
    q = (question or "").strip()
    if len(q) < 2:
        return False
    has_ood = any(k in q for k in _OOD_KEYWORDS)
    has_learning = any(k in q for k in _LEARNING_KEYWORDS)
    return bool(has_ood and not has_learning)


def _validate_one_phase(phase: dict) -> bool:
    """校验单个阶段：subject/mode 非空且枚举合法。"""
    if not phase or not isinstance(phase, dict):
        return False
    s = phase.get("subject")
    m = phase.get("mode")
    if not isinstance(s, list) or len(s) == 0:
        return False
    if not isinstance(m, list) or len(m) == 0:
        return False
    if not all(x in VALID_SUBJECTS for x in s):
        return False
    if not all(x in VALID_MODES for x in m):
        return False
    return True


def _validate_intent_json(obj) -> bool:
    """校验 LLM 输出：支持 sub_goals（有序多阶段）或单层 subject/mode。"""
    if not obj or not isinstance(obj, dict):
        return False
    sub_goals = obj.get("sub_goals")
    if isinstance(sub_goals, list) and len(sub_goals) > 0:
        return all(_validate_one_phase(p) for p in sub_goals)
    subject = obj.get("subject")
    mode = obj.get("mode")
    if not isinstance(subject, list) or len(subject) == 0:
        return False
    if not isinstance(mode, list) or len(mode) == 0:
        return False
    if not all(s in VALID_SUBJECTS for s in subject):
        return False
    if not all(m in VALID_MODES for m in mode):
        return False
    return True


def _default_goal(ctx: dict) -> GoalSpec:
    """默认目标：subject=[class], mode=[portrait]，单阶段 sub_goals，槽位从 context 继承。"""
    return GoalSpec(
        intent_type="overview",
        subject=["class"],
        mode=["portrait"],
        scope="all",
        sub_goals=[{"subject": ["class"], "mode": ["portrait"]}],
        is_out_of_domain=False,
        student_ids=list(ctx.get("selected_student_ids") or []),
        classes=list(ctx.get("classes") or []),
        majors=list(ctx.get("majors") or []),
        needs_clarification=False,
        clarification_question="",
    )


def _build_llm_user_prompt(question: str, ctx: dict) -> str:
    """组装 LLM 的用户输入，附带最近对话与待补全目标，提升多轮追问补槽命中率。"""
    q = (question or "").strip()
    recent_turns = list(ctx.get("recent_turns") or [])
    pending_goal = dict(ctx.get("pending_goal") or {})
    if not recent_turns and not pending_goal:
        return q

    lines = [f"当前用户输入：{q}"]
    if pending_goal:
        lines.append("上一轮待补全目标（pending_goal）如下：")
        lines.append(str(pending_goal))
    if recent_turns:
        lines.append("最近对话（最多6条）：")
        for t in recent_turns[-6:]:
            role = (t or {}).get("role") or "unknown"
            text = (t or {}).get("text") or ""
            lines.append(f"- {role}: {text}")
    lines.append("请结合上下文输出目标 JSON。")
    return "\n".join(lines)


def _parse_goal_with_llm(question: str, context=None) -> GoalSpec:
    """LLM 目标解析主路径；失败时 fallback 默认目标并打 WARNING 日志。"""
    ctx = normalize_context(context)
    q_preview = (question or "")[:200]
    _agent_logger.info("Goal parse LLM 调用开始，question 前200字: %s", q_preview)
    messages = [
        {"role": "system", "content": get_intent_parse_system_prompt()},
        *get_intent_few_shots(),
        {"role": "user", "content": _build_llm_user_prompt(question, ctx)},
    ]
    _agent_logger.debug(
        "Goal parse LLM: recent_turns=%d pending_goal=%s",
        len(ctx.get("recent_turns") or []),
        bool(ctx.get("pending_goal")),
    )
    client = get_default_llm_client()
    response = None
    try:
        response = client.chat_text_only(messages, max_tokens=MAX_TOKENS)
    except Exception:
        pass
    if response is None:
        _agent_logger.warning(
            "目标解析 LLM 不可用或调用失败，fallback 默认目标。question 前100字: %s",
            (question or "")[:100],
        )
        return _default_goal(ctx)
    text = LLMClient.extract_final_text(response)
    _agent_logger.info("Goal parse LLM 原始返回文本前200字: %s", (text or "")[:200])
    obj = extract_first_json_object(text) if text else None
    if obj and _validate_intent_json(obj):
        sub_goals_raw = obj.get("sub_goals")
        if isinstance(sub_goals_raw, list) and len(sub_goals_raw) > 0 and all(_validate_one_phase(p) for p in sub_goals_raw):
            # 复合意图：使用 sub_goals，并扁平化 subject/mode 供 plan 使用
            sub_goals = []
            subjects_ordered = []
            modes_ordered = []
            for p in sub_goals_raw:
                s = list(p["subject"])
                m = list(p["mode"])
                phase = {"subject": s, "mode": m}
                if p.get("title_id") is not None:
                    phase["title_id"] = p.get("title_id")
                if p.get("knowledge") is not None:
                    k = p.get("knowledge")
                    phase["knowledge"] = k[0] if isinstance(k, list) and k else (k if isinstance(k, str) else None)
                if p.get("time_window"):
                    phase["time_window"] = p.get("time_window", "") or ""
                sub_goals.append(phase)
                for x in s:
                    if x not in subjects_ordered:
                        subjects_ordered.append(x)
                for x in m:
                    if x not in modes_ordered:
                        modes_ordered.append(x)
            goal = GoalSpec(
                intent_type=obj.get("intent_type") or "overview",
                subject=subjects_ordered if subjects_ordered else ["class"],
                mode=modes_ordered if modes_ordered else ["portrait"],
                scope="all",
                sub_goals=sub_goals,
                is_out_of_domain=bool(obj.get("is_out_of_domain", False)),
                metric=obj.get("metric") or "",
                knowledge=next((p.get("knowledge") for p in sub_goals if p.get("knowledge") is not None), None),
                title_id=next((p.get("title_id") for p in sub_goals if p.get("title_id") is not None), obj.get("title_id")),
                student_ids=list(ctx.get("selected_student_ids") or []),
                classes=list(ctx.get("classes") or []),
                majors=list(ctx.get("majors") or []),
                time_window=obj.get("time_window") or (sub_goals[0].get("time_window") if sub_goals else ""),
                needs_clarification=bool(obj.get("needs_clarification", False)),
                clarification_question=(obj.get("clarification_question") or "").strip(),
            )
        else:
            # 单意图：从 subject/mode 构造单阶段 sub_goals
            s = list(obj["subject"])
            m = list(obj["mode"])
            phase = {"subject": s, "mode": m}
            if obj.get("title_id") is not None:
                phase["title_id"] = obj.get("title_id")
            k = obj.get("knowledge")
            knowledge_str = None
            if k is not None:
                knowledge_str = k[0] if isinstance(k, list) and k else (k if isinstance(k, str) else None)
                phase["knowledge"] = knowledge_str
            if obj.get("time_window"):
                phase["time_window"] = obj.get("time_window", "") or ""
            goal = GoalSpec(
                intent_type=obj.get("intent_type") or "overview",
                subject=s,
                mode=m,
                scope="all",
                sub_goals=[phase],
                is_out_of_domain=bool(obj.get("is_out_of_domain", False)),
                metric=obj.get("metric") or "",
                knowledge=knowledge_str,
                title_id=obj.get("title_id"),
                student_ids=list(ctx.get("selected_student_ids") or []),
                classes=list(ctx.get("classes") or []),
                majors=list(ctx.get("majors") or []),
                time_window=obj.get("time_window") or "",
                needs_clarification=bool(obj.get("needs_clarification", False)),
                clarification_question=(obj.get("clarification_question") or "").strip(),
            )
        goal.scope = _derive_scope(goal)
        if "student" in goal.subject and not goal.student_ids:
            goal.needs_clarification = True
            goal.clarification_question = goal.clarification_question or STUDENT_CLARIFICATION
        if _rule_detect_out_of_domain(question):
            goal.is_out_of_domain = True
        _agent_logger.info(
            "Goal parse LLM 解析通过 subject=%s mode=%s sub_goals=%d is_out_of_domain=%s",
            goal.subject, goal.mode, len(goal.sub_goals), goal.is_out_of_domain,
        )
        return goal
    _agent_logger.warning(
        "目标解析 LLM 输出非法或解析失败，fallback 默认目标。question 前100字: %s；原始 text 前200字: %s",
        (question or "")[:100],
        (text or "")[:200],
    )
    return _default_goal(ctx)


def _fill_subject_mode_scope(goal: GoalSpec) -> None:
    """根据 intent_type 填充 subject、mode，并推导 scope。"""
    it = goal.intent_type or "overview"
    if it == "trend":
        goal.subject = ["class"]
        goal.mode = ["trend"]
    elif it == "knowledge":
        goal.subject = ["knowledge"]
        goal.mode = ["portrait"]
    elif it == "student":
        goal.subject = ["student"]
        goal.mode = ["portrait"]
    elif it == "submission":
        goal.subject = ["student"]
        goal.mode = ["detail"]
    elif it == "cluster":
        goal.subject = ["class"]
        goal.mode = ["cluster"]
    else:
        goal.subject = ["class"]
        goal.mode = ["portrait"]
    goal.scope = _derive_scope(goal)


def _parse_goal_by_rules(question: str, context=None) -> GoalSpec:
    """关键词表兜底：INTENT_MATCHERS + 三轴填充，LLM 未配置时使用。"""
    text = (question or "").strip()
    q = text.lower()
    ctx = normalize_context(context)
    goal = GoalSpec(
        intent_type="overview",
        metric="",
        student_ids=list(ctx.get("selected_student_ids") or []),
        classes=list(ctx.get("classes") or []),
        majors=list(ctx.get("majors") or []),
    )
    for keywords, intent_type, metric, time_window in INTENT_MATCHERS:
        if any(k in q for k in keywords):
            goal.intent_type = intent_type
            goal.metric = metric
            goal.time_window = time_window or ""
            break
    for token in KNOWLEDGE_TOKENS:
        if token in text:
            goal.knowledge = token
            break
    if goal.intent_type == "student" and not goal.student_ids:
        goal.needs_clarification = True
        goal.clarification_question = STUDENT_CLARIFICATION
    _fill_subject_mode_scope(goal)
    goal.sub_goals = [{"subject": list(goal.subject), "mode": list(goal.mode)}]
    return goal


def parse_goal(question: str, context=None) -> GoalSpec:
    """目标解析入口：LLM 主路径，LLM 未配置时走规则兜底。"""
    client = get_default_llm_client()
    if client.config.is_available():
        return _parse_goal_with_llm(question, context)
    return _parse_goal_by_rules(question, context)

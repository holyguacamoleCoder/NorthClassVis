"""followup 模块单测：覆盖 merge_followup_goal 的关键分支与优先级。"""

from agent.intent.followup import _extract_student_ids
from agent.intent.followup import merge_followup_goal
from agent.intent.schemas import GoalSpec


def test_merge_followup_returns_parsed_goal_when_no_pending_goal():
    parsed = GoalSpec(intent_type="student", subject=["student"], mode=["portrait"], student_ids=["s001"])
    merged = merge_followup_goal(parsed, "看一下 s001", {"pending_needs_clarification": True})
    assert merged is parsed


def test_merge_followup_returns_parsed_goal_when_pending_not_clarifying():
    parsed = GoalSpec(intent_type="student", subject=["student"], mode=["portrait"], student_ids=["s001"])
    ctx = {
        "pending_goal": {
            "intent_type": "student",
            "subject": ["student"],
            "mode": ["portrait"],
            "student_ids": [],
        },
        "pending_needs_clarification": False,
    }
    merged = merge_followup_goal(parsed, "看一下 s001", ctx)
    assert merged is parsed


def test_merge_followup_prefers_parsed_goal_student_ids_over_question_extraction():
    parsed = GoalSpec(intent_type="student", subject=["student"], mode=["portrait"], student_ids=["s999"])
    ctx = {
        "pending_goal": {
            "intent_type": "student",
            "subject": ["student"],
            "mode": ["portrait"],
            "student_ids": [],
            "needs_clarification": True,
        },
        "pending_needs_clarification": True,
    }
    merged = merge_followup_goal(parsed, "看一下 s1001 和 s1002", ctx)
    assert merged.student_ids == ["s999"]
    assert merged.needs_clarification is False
    assert merged.clarification_question == ""


def test_merge_followup_keeps_pending_intent_axes_when_parsed_goal_is_default():
    parsed_default = GoalSpec()
    ctx = {
        "pending_goal": {
            "intent_type": "student",
            "subject": ["student"],
            "mode": ["portrait"],
            "metric": "student_profile",
            "student_ids": [],
            "needs_clarification": True,
            "clarification_question": "请提供 student_ids。",
        },
        "pending_needs_clarification": True,
    }
    merged = merge_followup_goal(parsed_default, "继续分析", ctx)
    assert merged.intent_type == "student"
    assert merged.subject == ["student"]
    assert merged.mode == ["portrait"]
    assert merged.metric == "student_profile"


def test_extract_student_ids_labeled_single_long_id():
    """带「学生编号」标签时整段提取，一个长学号不被拆成多个。"""
    ids = _extract_student_ids("学生编号：63eef37311aaac915a45")
    assert ids == ["63eef37311aaac915a45"]


def test_extract_student_ids_labeled_multiple_by_delimiter():
    """带标签时只按显式分隔符拆，得到多个 id。"""
    ids = _extract_student_ids("学号：63eef37311aaac915a45, 63abc999")
    assert "63eef37311aaac915a45" in ids
    assert "63abc999" in ids
    assert len(ids) == 2


def test_merge_followup_stays_in_clarification_when_slots_still_missing():
    parsed_default = GoalSpec()
    ctx = {
        "pending_goal": {
            "intent_type": "knowledge",
            "subject": ["knowledge"],
            "mode": ["portrait"],
            "knowledge": None,
            "needs_clarification": True,
            "clarification_question": "请提供知识点。",
        },
        "pending_needs_clarification": True,
    }
    merged = merge_followup_goal(parsed_default, "这个怎么样", ctx)
    assert merged.needs_clarification is True
    assert merged.clarification_question
    assert "知识点" in merged.clarification_question


def test_merge_followup_labeled_student_id_single():
    """用户回复「学生编号：63eef37311aaac915a45」时合并为一个 student_id，不拆成三个。"""
    parsed_default = GoalSpec()
    ctx = {
        "pending_goal": {
            "intent_type": "student",
            "subject": ["student"],
            "mode": ["portrait"],
            "student_ids": [],
            "needs_clarification": True,
        },
        "pending_needs_clarification": True,
    }
    merged = merge_followup_goal(parsed_default, "学生编号：63eef37311aaac915a45", ctx)
    assert merged.student_ids == ["63eef37311aaac915a45"]

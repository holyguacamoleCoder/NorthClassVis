"""目标解析：仅测规则兜底路径（不调 LLM）。"""
import pytest

from agent.common.context_utils import normalize_context
from agent.intent.goal_parser import parse_goal
from agent.intent.schemas import GoalSpec


@pytest.fixture
def empty_context():
    return normalize_context({})


@pytest.fixture(autouse=True)
def disable_llm(monkeypatch):
    """强制走规则路径：让 get_default_llm_client().config.is_available() 返回 False。"""
    class NoConfig:
        is_available = lambda self: False
    class NoLLM:
        config = NoConfig()
    monkeypatch.setattr("agent.intent.goal_parser.get_default_llm_client", lambda: NoLLM())


def test_parse_goal_rules_trend(empty_context):
    # 无 LLM 时走规则，关键词「趋势」-> trend
    goal = parse_goal("最近两周班级趋势怎么样？", empty_context)
    assert isinstance(goal, GoalSpec)
    assert "class" in goal.subject
    assert "trend" in goal.mode


def test_parse_goal_rules_knowledge(empty_context):
    goal = parse_goal("链表知识点掌握情况", empty_context)
    assert "knowledge" in goal.subject
    assert goal.knowledge == "链表"


def test_parse_goal_rules_student_no_ids_sets_clarification(empty_context):
    goal = parse_goal("学生画像", empty_context)
    assert "student" in goal.subject
    assert goal.needs_clarification is True
    assert goal.clarification_question


def test_parse_goal_context_inherits_student_ids(empty_context):
    ctx = normalize_context({"selected_student_ids": ["s001"]})
    goal = parse_goal("学生画像", ctx)
    assert goal.student_ids == ["s001"]

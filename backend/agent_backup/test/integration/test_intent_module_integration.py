"""intent 模块全过程集成测试：parse_goal -> validate -> clarifier。"""

import json

import pytest

from agent.common.context_utils import normalize_context
from agent.intent import apply_clarification
from agent.intent import build_clarification_question
from agent.intent import merge_followup_goal
from agent.intent import needs_clarification
from agent.intent import parse_goal
from agent.intent import validate


class _FakeConfig:
    def __init__(self, available):
        self._available = available

    def is_available(self):
        return self._available


class _FakeMessage:
    def __init__(self, content):
        self.content = content


class _FakeChoice:
    def __init__(self, content):
        self.message = _FakeMessage(content)


class _FakeResponse:
    def __init__(self, content):
        self.choices = [_FakeChoice(content)]


class _FakeLLMClient:
    def __init__(self, content, available=True):
        self._content = content
        self.config = _FakeConfig(available)
        self.last_messages = None
        self.last_max_tokens = None

    def chat_text_only(self, messages, max_tokens=200):
        self.last_messages = messages
        self.last_max_tokens = max_tokens
        return _FakeResponse(self._content)


class _NoLLMClient:
    config = _FakeConfig(False)


def _run_intent_pipeline(question, context=None):
    ctx = normalize_context(context or {})
    goal = parse_goal(question, ctx)
    validation = validate(goal)
    need_before = needs_clarification(goal)
    question_before = build_clarification_question(goal)
    apply_clarification(goal)
    return {
        "goal": goal,
        "validation": validation,
        "need_before": need_before,
        "question_before": question_before,
    }


@pytest.fixture
def disable_llm(monkeypatch):
    monkeypatch.setattr("agent.intent.goal_parser.get_default_llm_client", lambda: _NoLLMClient())


def test_intent_rules_pipeline_for_class_trend(disable_llm):
    """规则路径：班级趋势应完整走完解析、校验、追问判定，且无需澄清。"""
    result = _run_intent_pipeline("最近两周班级趋势怎么样？")

    goal = result["goal"]
    assert goal.intent_type == "trend"
    assert goal.subject == ["class"]
    assert goal.mode == ["trend"]
    assert goal.scope == "all"
    assert goal.time_window == "recent_2w"
    assert result["validation"].is_valid is True
    assert result["need_before"] is False
    assert result["question_before"] == ""
    assert goal.needs_clarification is False
    assert goal.clarification_question == ""


def test_intent_rules_pipeline_for_student_without_ids(disable_llm):
    """规则路径：学生问题缺少 student_ids 时，校验仍通过，但 clarifier 必须补出追问。"""
    result = _run_intent_pipeline("帮我看下学生画像")

    goal = result["goal"]
    assert goal.intent_type == "student"
    assert goal.subject == ["student"]
    assert goal.mode == ["portrait"]
    assert result["validation"].is_valid is True
    assert result["need_before"] is True
    assert "学生" in result["question_before"]
    assert goal.needs_clarification is True
    assert "学生" in goal.clarification_question


def test_intent_rules_pipeline_for_knowledge_without_slot(disable_llm):
    """规则路径：命中 knowledge 意图但未抽到具体知识点时，应进入知识点追问。"""
    result = _run_intent_pipeline("这个知识点掌握情况怎么样？")

    goal = result["goal"]
    assert goal.subject == ["knowledge"]
    assert goal.mode == ["portrait"]
    assert goal.knowledge is None
    assert result["validation"].is_valid is True
    assert result["need_before"] is True
    assert "知识点" in result["question_before"]
    assert goal.needs_clarification is True
    assert "知识点" in goal.clarification_question


def test_intent_followup_pipeline_merges_pending_goal(disable_llm):
    """多轮追问：上一轮 pending_goal 缺 student_ids，本轮回答后应完成补槽并退出追问。"""
    pending = {
        "intent_type": "student",
        "subject": ["student"],
        "mode": ["portrait"],
        "scope": "all",
        "student_ids": [],
        "knowledge": None,
        "needs_clarification": True,
        "clarification_question": "请提供 student_ids。",
    }
    ctx = {
        "pending_goal": pending,
        "pending_needs_clarification": True,
        "selected_student_ids": [],
    }
    parsed = parse_goal("看一下 s1001 和 s1002", ctx)
    merged = merge_followup_goal(parsed, "看一下 s1001 和 s1002", ctx)
    apply_clarification(merged)

    assert merged.subject == ["student"]
    assert merged.mode == ["portrait"]
    assert merged.student_ids == ["s1001", "s1002"]
    assert merged.needs_clarification is False
    assert merged.clarification_question == ""


@pytest.mark.llm
def test_intent_llm_pipeline_keeps_llm_clarification(monkeypatch):
    """LLM 分支：若 LLM 主动要求澄清并给出文案，完整流水线应保留该文案。"""
    fake_client = _FakeLLMClient(
        json.dumps(
            {
                "intent_type": "knowledge",
                "subject": ["knowledge"],
                "mode": ["portrait"],
                "scope": "all",
                "metric": "knowledge_score",
                "knowledge": None,
                "title_id": None,
                "student_ids": [],
                "classes": [],
                "majors": [],
                "time_window": "",
                "needs_clarification": True,
                "clarification_question": "请告诉我你想看的知识点名称。",
                "is_out_of_domain": False,
            },
            ensure_ascii=False,
        )
    )
    monkeypatch.setattr("agent.intent.goal_parser.get_default_llm_client", lambda: fake_client)

    result = _run_intent_pipeline("这个内容掌握得怎么样？")

    goal = result["goal"]
    assert result["validation"].is_valid is True
    assert result["need_before"] is True
    assert result["question_before"] == "请告诉我你想看的知识点名称。"
    assert goal.needs_clarification is True
    assert goal.clarification_question == "请告诉我你想看的知识点名称。"
    assert fake_client.last_messages is not None
    assert fake_client.last_max_tokens == 200


@pytest.mark.llm
def test_intent_llm_pipeline_uses_llm_json_and_context(monkeypatch):
    """LLM 分支：解析出的 JSON 应进入 validate/clarifier，并继承 context 中的 student_ids。"""
    fake_client = _FakeLLMClient(
        json.dumps(
            {
                "intent_type": "student",
                "subject": ["student"],
                "mode": ["portrait"],
                "scope": "all",
                "metric": "student_profile",
                "knowledge": None,
                "title_id": None,
                "student_ids": [],
                "classes": [],
                "majors": [],
                "time_window": "",
                "needs_clarification": False,
                "clarification_question": "",
                "is_out_of_domain": False,
            },
            ensure_ascii=False,
        )
    )
    monkeypatch.setattr("agent.intent.goal_parser.get_default_llm_client", lambda: fake_client)

    result = _run_intent_pipeline("看一下这个学生的画像", {"selected_student_ids": ["s-001"]})

    goal = result["goal"]
    assert result["validation"].is_valid is True
    assert goal.student_ids == ["s-001"]
    assert goal.scope == "individual"
    assert result["need_before"] is False
    assert goal.needs_clarification is False
    assert goal.clarification_question == ""


@pytest.mark.llm
def test_intent_llm_pipeline_falls_back_on_invalid_json(monkeypatch):
    """LLM 分支：当 LLM 给出非法枚举时，应回退到默认 goal，并继续走后续流水线。"""
    fake_client = _FakeLLMClient(
        json.dumps(
            {
                "intent_type": "overview",
                "subject": ["weather"],
                "mode": ["forecast"],
                "scope": "all",
                "needs_clarification": False,
                "clarification_question": "",
                "is_out_of_domain": False,
            },
            ensure_ascii=False,
        )
    )
    monkeypatch.setattr("agent.intent.goal_parser.get_default_llm_client", lambda: fake_client)

    result = _run_intent_pipeline("最近天气怎么样？", {"classes": ["Part"], "majors": ["All"]})

    goal = result["goal"]
    assert goal.intent_type == "overview"
    assert goal.subject == ["class"]
    assert goal.mode == ["portrait"]
    assert goal.classes == ["Part"]
    assert goal.majors == ["All"]
    assert result["validation"].is_valid is True
    assert result["need_before"] is False
    assert goal.needs_clarification is False

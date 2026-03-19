"""goal_parser 的 LLM 分支单测：用 fake LLM 覆盖 LLM 代码路径，不依赖外网。"""

import json

import pytest

from agent.common.context_utils import normalize_context
from agent.intent.goal_parser import parse_goal
from agent.intent.schemas import GoalSpec


class _FakeConfig:
    def is_available(self):
        return True


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
    config = _FakeConfig()

    def __init__(self, payload):
        self.payload = payload
        self.last_messages = None

    def chat_text_only(self, messages, max_tokens=200):
        self.last_messages = messages
        return _FakeResponse(self.payload)


@pytest.mark.llm
def test_parse_goal_llm_path_returns_valid_goal(monkeypatch):
    """LLM 分支：合法 JSON 应直接产出 GoalSpec。"""
    fake_client = _FakeLLMClient(
        json.dumps(
            {
                "intent_type": "trend",
                "subject": ["class"],
                "mode": ["trend"],
                "scope": "all",
                "metric": "weekly_score",
                "knowledge": None,
                "title_id": None,
                "student_ids": [],
                "classes": [],
                "majors": [],
                "time_window": "recent_2w",
                "needs_clarification": False,
                "clarification_question": "",
                "is_out_of_domain": False,
            },
            ensure_ascii=False,
        )
    )
    monkeypatch.setattr("agent.intent.goal_parser.get_default_llm_client", lambda: fake_client)

    goal = parse_goal("这周班里整体趋势怎么样？", normalize_context({}))
    assert isinstance(goal, GoalSpec)
    assert goal.subject == ["class"]
    assert goal.mode == ["trend"]
    assert goal.time_window == "recent_2w"
    assert fake_client.last_messages is not None


@pytest.mark.llm
def test_parse_goal_llm_path_knowledge_question(monkeypatch):
    """LLM 分支：知识点问句应解析出 knowledge 槽位。"""
    fake_client = _FakeLLMClient(
        json.dumps(
            {
                "intent_type": "knowledge",
                "subject": ["knowledge"],
                "mode": ["portrait"],
                "scope": "all",
                "metric": "knowledge_score",
                "knowledge": "链表",
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

    goal = parse_goal("链表这个知识点大家掌握得如何？", normalize_context({}))
    assert isinstance(goal, GoalSpec)
    assert goal.subject == ["knowledge"]
    assert goal.knowledge == "链表"


@pytest.mark.llm
def test_parse_goal_llm_path_out_of_domain(monkeypatch):
    """LLM 分支：非学情问题可被标记为 is_out_of_domain。"""
    fake_client = _FakeLLMClient(
        json.dumps(
            {
                "intent_type": "overview",
                "subject": ["class"],
                "mode": ["portrait"],
                "scope": "all",
                "metric": "",
                "knowledge": None,
                "title_id": None,
                "student_ids": [],
                "classes": [],
                "majors": [],
                "time_window": "",
                "needs_clarification": False,
                "clarification_question": "",
                "is_out_of_domain": True,
            },
            ensure_ascii=False,
        )
    )
    monkeypatch.setattr("agent.intent.goal_parser.get_default_llm_client", lambda: fake_client)

    goal = parse_goal("今天天气怎么样？", normalize_context({}))
    assert isinstance(goal, GoalSpec)
    assert goal.is_out_of_domain is True
    assert goal.subject == ["class"]
    assert goal.mode == ["portrait"]


@pytest.mark.llm
def test_parse_goal_rule_overrides_llm_out_of_domain(monkeypatch):
    """规则兜底：LLM 误将「今天天气怎么样？」判为学情时，规则仍强制 is_out_of_domain=True。"""
    fake_client = _FakeLLMClient(
        json.dumps(
            {
                "intent_type": "overview",
                "subject": ["class"],
                "mode": ["trend"],
                "scope": "all",
                "metric": "student_performance",
                "knowledge": None,
                "title_id": None,
                "student_ids": [],
                "classes": [],
                "majors": [],
                "time_window": "recent_2w",
                "needs_clarification": True,
                "clarification_question": "请问您具体想了解哪个学生的情况？",
                "is_out_of_domain": False,
            },
            ensure_ascii=False,
        )
    )
    monkeypatch.setattr("agent.intent.goal_parser.get_default_llm_client", lambda: fake_client)

    goal = parse_goal("今天天气怎么样？", normalize_context({}))
    assert goal.is_out_of_domain is True

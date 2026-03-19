"""intent + plan 联合集成测试：parse_goal -> validate -> clarifier -> build_task_graph -> validate_task_graph。

覆盖：规则/LLM 解析、追问短路、单阶段/多阶段 goal、CoT/ToT 策略选择、followup 补槽后建图；
      **完整 LLM 路径**：intent 用 LLM 解析 + plan 用 LLM（CoT/ToT）建图，同一流水线两次 LLM 调用。
"""

import json

import pytest

from agent.common.context_utils import normalize_context
from agent.intent import apply_clarification
from agent.intent import build_clarification_question
from agent.intent import merge_followup_goal
from agent.intent import needs_clarification
from agent.intent import parse_goal
from agent.intent import validate
from agent.intent.schemas import GoalSpec
from agent.plan import build_task_graph
from agent.plan import validate_task_graph
from agent.plan.task_graph import has_cycle


def _run_intent_plan_pipeline(question, context=None, apply_clarification_step=True):
    """intent 全流程 -> plan 建图。返回 goal、图、intent 校验、plan 校验。"""
    ctx = normalize_context(context or {})
    goal = parse_goal(question, ctx)
    intent_validation = validate(goal)
    need_before = needs_clarification(goal)
    _ = build_clarification_question(goal)
    if apply_clarification_step:
        apply_clarification(goal)
    graph = build_task_graph(goal)
    plan_validation = validate_task_graph(graph)
    return {
        "goal": goal,
        "graph": graph,
        "intent_validation": intent_validation,
        "plan_validation": plan_validation,
        "need_before": need_before,
    }


class _NoLLMConfig:
    def is_available(self):
        return False


class _NoLLMClient:
    config = _NoLLMConfig()


@pytest.fixture
def disable_llm(monkeypatch):
    monkeypatch.setattr("agent.intent.goal_parser.get_default_llm_client", lambda: _NoLLMClient())
    monkeypatch.setattr("agent.plan.planner.get_default_llm_client", lambda: _NoLLMClient())


# ---------- 规则 intent -> 单阶段 -> Simple 策略 ----------


def test_intent_plan_rules_single_phase(disable_llm):
    """规则解析出班级趋势 -> 无需追问 -> plan 单阶段 Simple -> 图 1 任务。"""
    result = _run_intent_plan_pipeline("最近两周班级趋势怎么样？")

    goal = result["goal"]
    assert goal.intent_type == "trend"
    assert goal.subject == ["class"]
    assert goal.mode == ["trend"]
    assert result["intent_validation"].is_valid is True
    assert result["need_before"] is False
    assert goal.needs_clarification is False

    graph = result["graph"]
    assert len(graph.tasks) == 1
    task = next(iter(graph.tasks.values()))
    assert "query_class" in task.required_tools
    assert task.tool_params.get("mode") == "trend"
    assert result["plan_validation"].is_valid is True
    assert has_cycle(graph) is False


# ---------- 追问短路：needs_clarification -> 空图 ----------


def test_intent_plan_short_circuit_when_needs_clarification(disable_llm):
    """学生画像无 student_ids -> intent 设 needs_clarification -> apply 后仍缺槽 -> build_task_graph 返回空图。"""
    result = _run_intent_plan_pipeline("帮我看下学生画像")

    goal = result["goal"]
    assert result["need_before"] is True
    assert goal.needs_clarification is True

    graph = result["graph"]
    assert len(graph.tasks) == 0
    assert result["plan_validation"].is_valid is True
    assert result["plan_validation"].reason == "空图"


def test_intent_plan_short_circuit_explicit_flag():
    """直接构造 needs_clarification=True 的 goal -> plan 短路，不依赖 intent 解析。"""
    goal = GoalSpec(
        subject=["student"],
        mode=["portrait"],
        student_ids=[],
        needs_clarification=True,
        clarification_question="请选择学生",
    )
    graph = build_task_graph(goal)
    assert len(graph.tasks) == 0


# ---------- 多阶段 goal（模拟 intent 产出 sub_goals）----------


def test_intent_plan_two_phases_goal(disable_llm):
    """两阶段 goal -> 走 CoT 或 Simple 按复杂度 -> 图至少 2 任务、有边。"""
    goal = GoalSpec(
        sub_goals=[
            {"subject": ["class"], "mode": ["trend"]},
            {"subject": ["student"], "mode": ["portrait"]},
        ],
        student_ids=["s1"],
    )
    graph = build_task_graph(goal)
    plan_validation = validate_task_graph(graph)

    assert len(graph.tasks) >= 2
    assert len(graph.edges) >= 1
    assert plan_validation.is_valid is True
    assert has_cycle(graph) is False


def test_intent_plan_three_phases_goal_no_llm(disable_llm):
    """三阶段 goal、无 LLM -> 降级 CoT -> 图 3 阶段、有依赖边。"""
    goal = GoalSpec(
        sub_goals=[
            {"subject": ["class"], "mode": ["trend"]},
            {"subject": ["class"], "mode": ["cluster"]},
            {"subject": ["student"], "mode": ["portrait"]},
        ],
        student_ids=["s1"],
    )
    graph = build_task_graph(goal)
    plan_validation = validate_task_graph(graph)

    assert len(graph.tasks) >= 3
    assert len(graph.edges) >= 2
    assert plan_validation.is_valid is True
    assert has_cycle(graph) is False


# ---------- Followup 补槽后建图 ----------


def test_intent_plan_followup_then_plan(disable_llm):
    """上一轮缺 student_ids，本轮 parse + merge_followup_goal + apply -> 补槽后 build_task_graph 非空。"""
    pending = {
        "intent_type": "student",
        "subject": ["student"],
        "mode": ["portrait"],
        "scope": "all",
        "student_ids": [],
        "knowledge": None,
        "needs_clarification": True,
        "clarification_question": "请提供学生。",
    }
    ctx = {
        "pending_goal": pending,
        "pending_needs_clarification": True,
        "selected_student_ids": [],
    }
    parsed = parse_goal("看一下 s1001 和 s1002", ctx)
    merged = merge_followup_goal(parsed, "看一下 s1001 和 s1002", ctx)
    apply_clarification(merged)

    assert merged.student_ids == ["s1001", "s1002"]
    assert merged.needs_clarification is False

    graph = build_task_graph(merged)
    assert len(graph.tasks) >= 1
    task = next(iter(graph.tasks.values()))
    assert task.tool_params.get("student_ids") == ["s1001", "s1002"]


# ---------- LLM intent 返回 sub_goals 后走 plan ----------


class _FakeLLMConfig:
    def __init__(self, available=True):
        self._available = available

    def is_available(self):
        return self._available


class _FakeLLMMessage:
    def __init__(self, content):
        self.content = content


class _FakeLLMChoice:
    def __init__(self, content):
        self.message = _FakeLLMMessage(content)


class _FakeLLMResponse:
    def __init__(self, content):
        self.choices = [_FakeLLMChoice(content)]


class _FakeLLMClientWithSubGoals:
    """返回带 sub_goals 的 intent JSON，触发 plan 多阶段策略。"""
    config = _FakeLLMConfig(True)

    def chat_text_only(self, messages, max_tokens=1024):
        return _FakeLLMResponse(
            json.dumps(
                {
                    "intent_type": "overview",
                    "subject": ["class", "student"],
                    "mode": ["trend", "portrait"],
                    "scope": "all",
                    "sub_goals": [
                        {"subject": ["class"], "mode": ["trend"], "title_id": None, "knowledge": None, "time_window": "recent_2w"},
                        {"subject": ["student"], "mode": ["portrait"], "title_id": None, "knowledge": None, "time_window": ""},
                    ],
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


@pytest.mark.llm
def test_intent_plan_llm_sub_goals_then_plan(monkeypatch):
    """Mock LLM 返回两阶段 sub_goals -> intent 产出多阶段 goal -> plan 无 LLM 建图至少 2 任务。"""
    monkeypatch.setattr("agent.intent.goal_parser.get_default_llm_client", lambda: _FakeLLMClientWithSubGoals())
    monkeypatch.setattr("agent.plan.planner.get_default_llm_client", lambda: _NoLLMClient())

    result = _run_intent_plan_pipeline("先看班级趋势再看学生画像", {"selected_student_ids": ["s1"]})

    goal = result["goal"]
    assert len(goal.sub_goals or []) == 2
    assert result["intent_validation"].is_valid is True

    graph = result["graph"]
    assert len(graph.tasks) >= 2
    assert len(graph.edges) >= 1
    assert has_cycle(graph) is False


# ---------- 完整 LLM 路径：intent LLM + plan CoT/ToT LLM（同一流水线两次 LLM）----------


class _FakeIntentThenCotLLM:
    """第一次调用返回 intent 两阶段 sub_goals，第二次返回 CoT ordered_phases。用于集成：question -> intent LLM -> goal -> plan CoT LLM -> graph。"""
    config = _FakeLLMConfig(True)

    def chat_text_only(self, messages, max_tokens=1024):
        content = json.dumps(messages, ensure_ascii=False) if isinstance(messages, list) else str(messages)
        if "ordered_phases" in content or ("phases" in content and "reasoning" in content):
            return _FakeLLMResponse(
                json.dumps(
                    {
                        "reasoning": "先整体趋势再学生画像，顺序合理。",
                        "ordered_phases": [
                            {"subject": ["class"], "mode": ["trend"]},
                            {"subject": ["student"], "mode": ["portrait"]},
                        ],
                    },
                    ensure_ascii=False,
                )
            )
        return _FakeLLMResponse(
            json.dumps(
                {
                    "intent_type": "overview",
                    "subject": ["class", "student"],
                    "mode": ["trend", "portrait"],
                    "scope": "all",
                    "sub_goals": [
                        {"subject": ["class"], "mode": ["trend"], "title_id": None, "knowledge": None, "time_window": "recent_2w"},
                        {"subject": ["student"], "mode": ["portrait"], "title_id": None, "knowledge": None, "time_window": ""},
                    ],
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


@pytest.mark.llm
def test_intent_plan_full_llm_path_cot(monkeypatch):
    """集成：question -> intent LLM(2 阶段) -> goal -> plan CoT LLM(ordered_phases) -> 图至少 2 任务、有边、reason 带 CoT。"""
    fake = _FakeIntentThenCotLLM()
    monkeypatch.setattr("agent.intent.goal_parser.get_default_llm_client", lambda: fake)
    monkeypatch.setattr("agent.plan.planner.get_default_llm_client", lambda: fake)

    result = _run_intent_plan_pipeline("先看班级趋势再看学生画像", {"selected_student_ids": ["s1"]})

    goal = result["goal"]
    assert len(goal.sub_goals or []) == 2
    graph = result["graph"]
    assert len(graph.tasks) >= 2
    assert len(graph.edges) >= 1
    assert has_cycle(graph) is False
    reasons = [t.reason for t in graph.tasks.values()]
    assert any("CoT" in r or "chain" in r.lower() or "顺序" in r for r in reasons)


class _FakeIntentThenTotLLM:
    """第一次调用返回 intent 三阶段 sub_goals，第二次返回 ToT selected_plans。用于集成：question -> intent LLM -> goal -> plan ToT LLM -> graph。"""
    config = _FakeLLMConfig(True)

    def chat_text_only(self, messages, max_tokens=1024):
        content = json.dumps(messages, ensure_ascii=False) if isinstance(messages, list) else str(messages)
        if "selected_plans" in content or "path_phases" in content or "plan_candidates" in content:
            return _FakeLLMResponse(
                json.dumps(
                    {
                        "selected_plans": [
                            {"plan_id": "p0", "score": 0.92, "reason": "先整体后个体，路径合理"},
                        ],
                    },
                    ensure_ascii=False,
                )
            )
        return _FakeLLMResponse(
            json.dumps(
                {
                    "intent_type": "overview",
                    "subject": ["class", "student"],
                    "mode": ["trend", "cluster", "portrait"],
                    "scope": "all",
                    "sub_goals": [
                        {"subject": ["class"], "mode": ["trend"], "title_id": None, "knowledge": None, "time_window": ""},
                        {"subject": ["class"], "mode": ["cluster"], "title_id": None, "knowledge": None, "time_window": ""},
                        {"subject": ["student"], "mode": ["portrait"], "title_id": None, "knowledge": None, "time_window": ""},
                    ],
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


@pytest.mark.llm
def test_intent_plan_full_llm_path_tot(monkeypatch):
    """集成：question -> intent LLM(3 阶段) -> goal -> plan ToT LLM(selected_plans) -> 图至少 3 任务、有边、reason 带 ToT。"""
    fake = _FakeIntentThenTotLLM()
    monkeypatch.setattr("agent.intent.goal_parser.get_default_llm_client", lambda: fake)
    monkeypatch.setattr("agent.plan.planner.get_default_llm_client", lambda: fake)

    result = _run_intent_plan_pipeline("先班级趋势和聚类，再学生画像", {"selected_student_ids": ["s1"]})

    goal = result["goal"]
    assert len(goal.sub_goals or []) == 3
    graph = result["graph"]
    assert len(graph.tasks) >= 3
    assert len(graph.edges) >= 2
    assert has_cycle(graph) is False
    reasons = [t.reason for t in graph.tasks.values()]
    assert any("ToT[" in r or "p0" in r for r in reasons)

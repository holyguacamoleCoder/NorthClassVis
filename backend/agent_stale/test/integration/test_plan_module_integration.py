"""plan+execution 模块全过程集成测试：build_task_graph -> validate -> schedule -> execution compile。"""

import json
from copy import deepcopy

import pytest

from agent.intent.schemas import GoalSpec
from agent.execution import compile_execution_plan_to_steps
from agent.execution import compile_plan
from agent.execution import extract_tool_results
from agent.execution import schedule
from agent.plan import build_task_graph
from agent.plan import validate_task_graph


class _NoLLMConfig:
    def is_available(self):
        return False


class _NoLLMClient:
    config = _NoLLMConfig()


@pytest.fixture(autouse=True)
def disable_tot_by_default(monkeypatch):
    monkeypatch.setattr("agent.plan.planner.get_default_llm_client", lambda: _NoLLMClient())


def _run_plan_pipeline(goal):
    graph = build_task_graph(goal)
    validation = validate_task_graph(graph)
    execution_plan = schedule(graph)
    steps_from_plan = compile_execution_plan_to_steps(execution_plan)
    steps_from_compile = compile_plan(deepcopy(goal))
    return {
        "graph": graph,
        "validation": validation,
        "execution_plan": execution_plan,
        "steps_from_plan": steps_from_plan,
        "steps_from_compile": steps_from_compile,
    }


def test_plan_pipeline_for_class_trend():
    """class/trend 应完整经历建图、校验、调度、编译，并得到 query_class。"""
    result = _run_plan_pipeline(GoalSpec(subject=["class"], mode=["trend"]))

    graph = result["graph"]
    assert len(graph.tasks) == 1
    task = next(iter(graph.tasks.values()))
    assert task.required_tools == ["query_class"]
    assert task.tool_params == {"mode": "trend"}

    assert result["validation"].is_valid is True
    assert len(result["execution_plan"].batches) == 1
    assert result["execution_plan"].batches[0].task_ids == [task.task_id]

    assert len(result["steps_from_plan"]) == 1
    assert result["steps_from_plan"][0].tool == "query_class"
    assert result["steps_from_plan"][0].params == {"mode": "trend"}
    assert [s.to_dict() for s in result["steps_from_compile"]] == [s.to_dict() for s in result["steps_from_plan"]]


def test_plan_pipeline_for_class_detail():
    """class/detail 应落到 query_class(mode=detail)，并完整经历建图、校验、调度、编译。"""
    result = _run_plan_pipeline(GoalSpec(subject=["class"], mode=["detail"]))

    graph = result["graph"]
    assert len(graph.tasks) == 1
    task = next(iter(graph.tasks.values()))
    assert task.required_tools == ["query_class"]
    assert task.tool_params == {"mode": "detail"}

    assert result["validation"].is_valid is True
    assert len(result["execution_plan"].batches) == 1
    assert result["execution_plan"].batches[0].task_ids == [task.task_id]

    assert len(result["steps_from_plan"]) == 1
    assert result["steps_from_plan"][0].tool == "query_class"
    assert result["steps_from_plan"][0].params == {"mode": "detail"}
    assert [s.to_dict() for s in result["steps_from_compile"]] == [s.to_dict() for s in result["steps_from_plan"]]


def test_plan_pipeline_for_student_detail_with_two_steps():
    """student/detail 应生成两个子任务，并在同一并行批次中展平为两个步骤。"""
    result = _run_plan_pipeline(GoalSpec(subject=["student"], mode=["detail"], student_ids=["s1"]))

    graph = result["graph"]
    assert len(graph.tasks) == 2
    assert result["validation"].is_valid is True

    batches = result["execution_plan"].batches
    assert len(batches) == 1
    assert batches[0].parallel is True
    assert len(batches[0].task_ids) == 2

    steps = result["steps_from_plan"]
    assert len(steps) == 2
    assert [s.tool for s in steps] == ["query_student", "query_student"]
    assert steps[0].params["student_ids"] == ["s1"]
    assert steps[1].params["student_ids"] == ["s1"]
    assert steps[0].params["mode"] == "tree"
    assert steps[1].params["mode"] == "detail"

    compiled = result["steps_from_compile"]
    assert [s.to_dict() for s in compiled] == [s.to_dict() for s in steps]


def test_plan_pipeline_short_circuits_when_goal_needs_clarification():
    """needs_clarification=True 时，plan 模块应在最前面短路，不再生成任务。"""
    result = _run_plan_pipeline(GoalSpec(subject=["student"], mode=["portrait"], needs_clarification=True))

    assert result["graph"].tasks == {}
    assert result["validation"].is_valid is True
    assert result["validation"].reason == "空图"
    assert result["execution_plan"].batches == []
    assert result["steps_from_plan"] == []
    assert result["steps_from_compile"] == []


def test_plan_pipeline_fallback_for_unmapped_subject_mode():
    """当 subject/mode 合法但查不到映射时，plan 应落到 fallback，而不是返回空步骤。"""
    result = _run_plan_pipeline(GoalSpec(subject=["question"], mode=["cluster"]))

    graph = result["graph"]
    assert len(graph.tasks) == 1
    task = next(iter(graph.tasks.values()))
    assert task.required_tools == ["query_class"]
    assert task.tool_params == {"mode": "trend"}
    assert task.reason == "overview fallback"

    assert result["validation"].is_valid is True
    assert len(result["steps_from_compile"]) == 1
    assert result["steps_from_compile"][0].tool == "query_class"
    assert result["steps_from_compile"][0].params == {"mode": "trend"}


def test_plan_pipeline_extract_tool_results_from_compiled_steps():
    """完整编译出的步骤应能被 runner 结果规范化为 ToolResult。"""
    result = _run_plan_pipeline(GoalSpec(subject=["question"], mode=["detail"], title_id="5"))

    steps = result["steps_from_compile"]
    assert len(steps) == 2
    assert [s.params["mode"] for s in steps] == ["timeline", "dist"]

    raw_tool_results = []
    for idx, step in enumerate(steps):
        raw_tool_results.append(
            {
                "tool": step.tool,
                "input": step.params,
                "status": "ok",
                "summary": f"summary-{idx}",
                "evidence": [],
                "visual_hints": [],
                "duration_ms": idx + 1,
                "coverage": {"covered": True},
                "quality": {"score": 1.0},
                "error": "",
            }
        )

    normalized = extract_tool_results(raw_tool_results)
    assert len(normalized) == 2
    assert normalized[0].tool == "query_question"
    assert normalized[0].params["title_id"] == "5"
    assert normalized[0].params["limit"] == 20
    assert normalized[0].summary == "summary-0"
    assert normalized[1].params["mode"] == "dist"


class _FakeYesConfig:
    def is_available(self):
        return True


class _FakeMsg:
    def __init__(self, content):
        self.content = content


class _FakeChoice:
    def __init__(self, content):
        self.message = _FakeMsg(content)


class _FakeResp:
    def __init__(self, content):
        self.choices = [_FakeChoice(content)]


class _FakeTotClient:
    """ToT 路径模式：返回 selected_plans（多方案评选），使三阶段 goal 走 ToT 策略。"""
    config = _FakeYesConfig()

    def chat_text_only(self, messages, max_tokens=1024):
        _ = messages, max_tokens
        return _FakeResp(
            json.dumps(
                {
                    "selected_plans": [
                        {"plan_id": "p0", "score": 0.9, "reason": "先整体后个体，顺序合理"},
                        {"plan_id": "p1", "score": 0.5, "reason": "备选"},
                    ]
                },
                ensure_ascii=False,
            )
        )


@pytest.mark.llm
def test_plan_pipeline_with_tot_strategy(monkeypatch):
    """三阶段 goal + LLM 可用 -> 走 ToT 策略，任务 reason 带 ToT 打分痕迹。"""
    monkeypatch.setattr("agent.plan.planner.get_default_llm_client", lambda: _FakeTotClient())
    goal = GoalSpec(
        sub_goals=[
            {"subject": ["class"], "mode": ["trend"]},
            {"subject": ["class"], "mode": ["cluster"]},
            {"subject": ["student"], "mode": ["portrait"]},
        ],
        student_ids=["s1"],
    )
    result = _run_plan_pipeline(goal)

    graph = result["graph"]
    assert len(graph.tasks) >= 3
    reasons = [t.reason for t in graph.tasks.values()]
    assert any("ToT[" in r or "p0" in r for r in reasons)

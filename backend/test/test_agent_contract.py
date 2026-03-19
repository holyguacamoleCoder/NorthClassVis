# 验证 Agent 接口与前端契约一致：响应顶层直接为 answer/evidence/actions/visual_links/trace，无 data 包裹。

import sys
import os
import importlib.util

current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(current_dir)
sys.path.insert(0, backend_dir)

import pytest
import json


pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("numpy") is None,
    reason="numpy 未安装，跳过依赖数据分析栈的 agent 契约测试",
)


@pytest.fixture
def client():
    try:
        from app import app
    except Exception as e:
        if "numpy" in str(e).lower() or "pandas" in str(e).lower():
            pytest.skip(f"数据分析依赖未就绪，跳过契约测试: {e}")
        raise
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_agent_query_returns_contract(client):
    rv = client.post(
        "/api/agent/query",
        json={"question": "最近两周班级整体表现如何？", "context": {}},
        content_type="application/json",
    )
    assert rv.status_code == 200
    data = rv.get_json()
    assert data is not None
    assert "answer" in data
    assert "evidence" in data
    assert "actions" in data
    assert "visual_links" in data
    assert "trace" in data
    assert "data" not in data, "响应应为顶层 answer/evidence/actions/visual_links/trace，不包 data"
    assert isinstance(data["answer"], str)
    assert isinstance(data["evidence"], list)
    assert isinstance(data["actions"], list)
    assert isinstance(data["visual_links"], list)
    assert isinstance(data["trace"], dict)
    assert "steps" in data["trace"]
    assert isinstance(data["trace"]["steps"], list)
    for step in data["trace"]["steps"]:
        assert "tool" in step
        assert "summary" in step
        assert "params" in step
        # params 须可 JSON 序列化（前端契约）
        import json as _json
        _json.dumps(step["params"])
    for ev in data["evidence"]:
        assert "tool" in ev
        assert "summary" in ev
    for link in data["visual_links"]:
        assert "view" in link
        assert "params" in link
        assert isinstance(link["params"], dict)
    # 默认主路径为 compiler_v1，步骤为工具名
    if data["trace"]["steps"]:
        known_tools = {
            "get_context_filter",
            "query_weekly_trend",
            "list_questions",
            "get_student_portrait",
            "query_submissions",
            "get_cluster_everyone",
        }
        assert any(step.get("tool") in known_tools for step in data["trace"]["steps"])


def test_agent_query_compiler_mode_returns_contract(client):
    rv = client.post(
        "/api/agent/query?mode=compiler_v1",
        json={"question": "最近两周班级整体表现如何？", "context": {}},
        content_type="application/json",
    )
    assert rv.status_code == 200
    data = rv.get_json()
    assert data is not None
    assert "answer" in data and isinstance(data["answer"], str)
    assert "trace" in data and isinstance(data["trace"], dict)
    assert "steps" in data["trace"] and isinstance(data["trace"]["steps"], list)
    for step in data["trace"]["steps"]:
        assert "tool" in step
        assert "summary" in step
        assert "params" in step
        assert "coverage" in step
        assert "quality" in step
        assert isinstance(step["coverage"], dict)
        assert isinstance(step["quality"], dict)


def test_agent_query_compiler_student_needs_clarify(client):
    rv = client.post(
        "/api/agent/query?mode=compiler_v1",
        json={"question": "请给我学生个体诊断", "context": {}},
        content_type="application/json",
    )
    assert rv.status_code == 200
    data = rv.get_json()
    assert "answer" in data
    assert "student_ids" in data["answer"] or "当前数据不足" in data["answer"]


def test_agent_query_empty_question_returns_400(client):
    rv = client.post(
        "/api/agent/query",
        json={"context": {}},
        content_type="application/json",
    )
    assert rv.status_code == 400
    data = rv.get_json()
    assert data and "answer" in data


def test_agent_golden_cases_contract(client):
    with open("test/agent_golden_cases.json", "r", encoding="utf-8") as f:
        cases = json.load(f)
    for case in cases:
        mode = case.get("mode") or "compiler_v1"
        rv = client.post(
            f"/api/agent/query?mode={mode}",
            json={"question": case.get("question"), "context": case.get("context") or {}},
            content_type="application/json",
        )
        assert rv.status_code == 200
        data = rv.get_json()
        assert isinstance(data, dict)
        assert isinstance(data.get("answer"), str)
        assert isinstance(data.get("trace"), dict)
        assert isinstance((data.get("trace") or {}).get("steps"), list)

        expected_tools = case.get("expect_trace_tools_any_of") or []
        if expected_tools:
            got_tools = [s.get("tool") for s in data["trace"]["steps"]]
            assert any(t in got_tools for t in expected_tools)

        expect_texts = case.get("expect_answer_contains_any_of") or []
        if expect_texts:
            assert any(t in data["answer"] for t in expect_texts)

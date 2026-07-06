import importlib.util
import json
import sys
from pathlib import Path

import pytest

import runtime_bootstrap  # noqa: F401, E402

BACKEND_ROOT = Path(__file__).resolve().parents[2]
AGENT_ROOT = BACKEND_ROOT / "agent"

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("numpy") is None,
    reason="numpy 未安装，跳过数据分析栈测试",
)

from data.filter_context import FilterContext  # noqa: E402
from data.visual_links import validate_links  # noqa: E402
from permission import CapabilityMode, filter_tools  # noqa: E402
from tools.definitions.schemas import TOOLS  # noqa: E402
from tools.handlers.context_tools import (  # noqa: E402
    run_build_visual_links,
    run_get_current_filter_context,
)
from tools.handlers.data_tools import run_query_data  # noqa: E402
from tools.runtime.data.inject import inject_data_tool_context  # noqa: E402


@pytest.fixture
def data_dir():
    return BACKEND_ROOT.parent / "data"


def test_get_current_filter_context_default():
    raw = run_get_current_filter_context()
    payload = json.loads(raw)
    assert payload["classes"]
    assert isinstance(payload["classes"], list)
    json.dumps(payload)


def test_filter_context_from_http_body():
    fc = FilterContext.from_http_body(
        {
            "classes": ["Class1"],
            "majors": ["All"],
            "week_range": [10, 25],
            "selected_student_ids": ["abc123"],
        }
    )
    assert fc is not None
    assert fc.classes == ("Class1",)
    assert fc.week_range == (10, 25)
    assert fc.selected_student_ids == ("abc123",)
    assert fc.source == "http_body"
    assert fc.to_resolve_params()["classes"] == ["Class1"]
    assert fc.to_resolve_params()["student_ids"] == ["abc123"]


def test_build_visual_links_valid_three(data_dir, monkeypatch):
    monkeypatch.chdir(BACKEND_ROOT.parent)
    raw = run_build_visual_links(
        links=[
            {"view": "WeekView", "params": {"kind": 1}},
            {"view": "QuestionView", "params": {"knowledge": "链表"}},
            {"view": "StudentView", "params": {"student_ids": ["8b6d1125760bd3939b6e"]}},
        ],
    )
    payload = json.loads(raw)
    assert len(payload["visual_links"]) == 3
    assert not payload["rejected"]
    json.dumps(payload)


def test_build_visual_links_rejects_bad_view():
    raw = run_build_visual_links(
        links=[
            {"view": "BadView", "params": {}},
            {"view": "QuestionView", "params": {}},
        ],
    )
    payload = json.loads(raw)
    assert payload["rejected"]
    views = {item["view"] for item in payload["rejected"]}
    assert "BadView" in views
    assert "QuestionView" in views


def test_build_visual_links_question_view_title_ids():
    raw = run_build_visual_links(
        links=[
            {
                "view": "QuestionView",
                "params": {
                    "title_ids": [
                        "Question_QRm48lXxzdP7Tn1WgNOf",
                        "Question_UXqN1F7G3Sbldz02vZne",
                    ],
                },
            },
        ],
    )
    payload = json.loads(raw)
    assert len(payload["visual_links"]) == 1
    params = payload["visual_links"][0]["params"]
    assert len(params["title_ids"]) == 2
    assert "knowledge" not in params


def test_normalize_question_params_maps_short_codes_to_knowledge():
    from data.visual_links import normalize_question_params

    out, err = normalize_question_params({"title_ids": ["b3C9s", "r8S3g"]})
    assert err is None
    assert out is not None
    assert out.get("knowledge_ids") == ["b3C9s", "r8S3g"]
    assert "title_ids" not in out


def test_build_visual_links_rejects_placeholder_knowledge():
    raw = run_build_visual_links(
        links=[{"view": "QuestionView", "params": {"knowledge": "some_knowledge"}}],
    )
    payload = json.loads(raw)
    assert payload["rejected"]


def test_build_visual_links_injects_week_range_from_filter_context(data_dir, monkeypatch):
    monkeypatch.chdir(BACKEND_ROOT.parent)
    fc = FilterContext(classes=("Class1",), week_range=(10, 13), source="http_body")
    raw = run_build_visual_links(
        links=[{"view": "WeekView", "params": {}}],
        _filter_context=fc,
    )
    payload = json.loads(raw)
    assert len(payload["visual_links"]) == 1
    assert payload["visual_links"][0]["params"]["week_range"] == [10, 13]
    ids = payload["visual_links"][0]["params"].get("student_ids") or []
    assert len(ids) >= 2
    assert all(len(str(s)) >= 16 for s in ids)
    assert "typical_student_ids" in payload


def test_build_visual_links_replaces_placeholder_student_ids(data_dir, monkeypatch):
    monkeypatch.chdir(BACKEND_ROOT.parent)
    fc = FilterContext(classes=("Class2",), week_range=(13, 15), source="http_body")
    raw = run_build_visual_links(
        links=[
            {
                "view": "WeekView",
                "params": {
                    "student_ids": ["student1", "student2", "student3"],
                    "week_range": [13, 15],
                },
            }
        ],
        archetype="class_overview",
        _filter_context=fc,
    )
    payload = json.loads(raw)
    params = payload["visual_links"][0]["params"]
    ids = params.get("student_ids") or []
    assert ids
    assert "student1" not in ids
    assert all(s.isalnum() and len(s) >= 16 for s in ids)
    assert any("代表学生" in w or "占位" in w for w in payload.get("warnings") or [])


def test_build_visual_links_no_student_ids_warning_when_single_selected():
    fc = FilterContext(
        classes=("Class1",),
        week_range=(0, 15),
        selected_student_ids=("stu1",),
        source="http_body",
    )
    raw = run_build_visual_links(
        links=[{"view": "WeekView", "params": {"week_range": [0, 15]}}],
        _filter_context=fc,
    )
    payload = json.loads(raw)
    assert not any("student_ids" in w and "建议" in w for w in payload.get("warnings") or [])


def test_build_visual_links_archetype_warnings():
    raw = run_build_visual_links(
        links=[
            {"view": "StudentView", "params": {"student_ids": ["x"]}},
        ],
        archetype="student_diagnosis",
    )
    payload = json.loads(raw)
    assert len(payload["visual_links"]) == 1
    assert any("missing recommended view" in w for w in payload["warnings"])


def test_consolidate_three_week_view_links():
    result = validate_links(
        [
            {"view": "WeekView", "params": {"kind": 1}},
            {"view": "WeekView", "params": {"kind": 2}},
            {"view": "WeekView", "params": {"kind": 3}},
        ],
    )
    assert len(result["visual_links"]) == 1
    assert result["visual_links"][0]["params"] == {}
    assert any("合并" in w for w in result["warnings"])


def test_week_view_cluster_normalization():
    result = validate_links(
        [{"view": "WeekView", "params": {"cluster": 2}}],
    )
    link = result["visual_links"][0]
    assert link["params"] == {"kind": 3}


def test_filter_tools_consult_excludes_build_links():
    names = {t["function"]["name"] for t in filter_tools(TOOLS, CapabilityMode.CONSULT)}
    assert "get_current_filter_context" in names
    assert "build_visual_links" not in names


def test_filter_tools_analyze_includes_adapter_tools():
    names = {t["function"]["name"] for t in filter_tools(TOOLS, CapabilityMode.ANALYZE)}
    assert "get_current_filter_context" in names
    assert "build_visual_links" in names


def test_inject_filter_context_into_query(data_dir, monkeypatch):
    monkeypatch.chdir(BACKEND_ROOT.parent)
    fc = FilterContext(classes=("Class1",), source="session")
    args = inject_data_tool_context(
        "query_data",
        {"resource": "submit_record"},
        analysis_context=None,
        batch_snapshots=[],
        filter_context=fc,
    )
    assert args.get("_filter_context") is fc
    raw = run_query_data(**args, data_dir=data_dir)
    assert not raw.startswith("Error:")
    payload = json.loads(raw)
    assert payload.get("meta")


def test_inject_teacher_message_into_query_data():
    from loop_state import AnalysisToolContext

    ctx = AnalysisToolContext(
        session_id="s1",
        user_turn=1,
        current_user_message="Class2 第 13-15 周班级学情总览",
        turn_snapshots=[],
        working_active_ref=None,
    )
    args = inject_data_tool_context(
        "query_data",
        {"resource": "week_aggregation", "classes": ["Class2"]},
        analysis_context=ctx,
        batch_snapshots=[],
        filter_context=FilterContext(classes=("Class1",), source="http_body"),
    )
    assert args.get("_teacher_message") == "Class2 第 13-15 周班级学情总览"


def test_inject_query_class2_submit_record_e2e(data_dir, monkeypatch):
    """Production path: inject → run_query_data matches session b99bab4ec9eb fix."""
    from loop_state import AnalysisToolContext

    monkeypatch.chdir(BACKEND_ROOT.parent)
    fc = FilterContext(
        classes=("Class1",),
        selected_student_ids=("5d89810b20079366fcc2", "8b6d1125760bd3939b6e"),
        majors=("J23517", "J40192"),
        week_range=(13, 15),
        source="http_body",
    )
    ctx = AnalysisToolContext(
        session_id="sess-e2e",
        user_turn=1,
        current_user_message="Class2 这学期第 13 到 15 周整体学得怎么样",
    )
    args = inject_data_tool_context(
        "query_data",
        {"resource": "submit_record", "class": "Class2", "limit": 0},
        analysis_context=ctx,
        batch_snapshots=[],
        filter_context=fc,
    )
    raw = run_query_data(**args, data_dir=data_dir)
    assert not raw.startswith("Error:")
    payload = json.loads(raw)
    meta = payload.get("meta") or {}
    assert meta.get("nav_scope_suppressed") is True
    assert int(meta.get("rows_scanned") or 0) > 100
    assert meta.get("ui_selected_students") is None


def test_merge_resolve_params_explicit_wins():
    fc = FilterContext(classes=("Class1",), source="session")
    merged = fc.merge_resolve_params({"classes": ["Class2"]})
    assert merged["classes"] == ["Class2"]


def test_trace_params_json_serializable():
    raw = run_build_visual_links(
        links=[{"view": "WeekView", "params": {"kind": 2}}],
        archetype="class_overview",
    )
    payload = json.loads(raw)
    json.dumps({"tool": "build_visual_links", "params": payload})

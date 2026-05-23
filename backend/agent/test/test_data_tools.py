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
pytest.importorskip("pandas")

from data import (  # noqa: E402
    QuerySpec,
    execute_query,
    load_result,
    validate_tabular_result,
)
from data.exceptions import InvalidParameterError  # noqa: E402
from data.param_validation import normalize_query_resource  # noqa: E402
from permission import CapabilityMode, filter_tools  # noqa: E402
from tools.definitions.schemas import TOOLS  # noqa: E402
from tools.handlers.data_tools import run_aggregate_data, run_inspect_schema, run_query_data  # noqa: E402


@pytest.fixture
def data_dir():
    return BACKEND_ROOT.parent / "data"


def test_inspect_schema_student_info(data_dir, monkeypatch):
    monkeypatch.chdir(BACKEND_ROOT.parent)
    raw = run_inspect_schema(resource="student_info", data_dir=data_dir)
    assert not raw.startswith("Error:")
    payload = json.loads(raw)
    assert payload["resource"] == "student_info"
    assert len(payload["columns"]) > 0
    assert payload["row_count_estimate"] > 0
    names = {c["name"] for c in payload["columns"]}
    assert "student_ID" in names


def test_inspect_schema_submit_record(data_dir, monkeypatch):
    monkeypatch.chdir(BACKEND_ROOT.parent)
    raw = run_inspect_schema(resource="submit_record", **{"class": "Class1"}, data_dir=data_dir)
    payload = json.loads(raw)
    assert payload["resource"] == "submit_record"
    assert payload["row_count_estimate"] > 0
    names = {c["name"] for c in payload["columns"]}
    assert "knowledge" in names
    assert "major" in names


def test_inspect_schema_submit_record_joined_alias(data_dir, monkeypatch):
    monkeypatch.chdir(BACKEND_ROOT.parent)
    raw = run_inspect_schema(resource="submit_record_joined", classes=["Class1"], data_dir=data_dir)
    payload = json.loads(raw)
    assert payload["resource"] == "submit_record"
    notes = payload.get("normalization_notes") or []
    assert any("submit_record" in n for n in notes)


def test_query_data_where_limit(data_dir, monkeypatch):
    monkeypatch.chdir(BACKEND_ROOT.parent)
    raw = run_query_data(
        resource="student_info",
        select=["student_ID", "major"],
        where={"op": "eq", "field": "major", "value": payload_major(data_dir)},
        limit=5,
        data_dir=data_dir,
    )
    assert not raw.startswith("Error:")
    result = json.loads(raw)
    validate_tabular_result(result)
    assert len(result["rows"]) <= 5


def payload_major(data_dir):
    from data.registry import resolve

    df = resolve("student_info", data_dir=data_dir).load()
    return df["major"].iloc[0]


def test_query_data_large_result_truncated(data_dir, monkeypatch):
    monkeypatch.chdir(BACKEND_ROOT.parent)
    spec = QuerySpec(
        resource="submit_record",
        select=["student_ID", "score"],
        resolve_params={"classes": ["Class1"]},
        limit=200,
    )
    result = execute_query(spec, data_dir=data_dir, preview_limit=10)
    validate_tabular_result(result)
    assert result["meta"]["truncated"] is True
    assert len(result["rows"]) <= 10
    ref = result["meta"]["result_ref"]
    assert ref
    full = load_result(ref)
    assert len(full["rows"]) > len(result["rows"])


def test_aggregate_data_on_result_ref(data_dir, monkeypatch):
    monkeypatch.chdir(BACKEND_ROOT.parent)
    spec = QuerySpec(
        resource="submit_record",
        select=["score"],
        resolve_params={"classes": ["Class1"]},
        limit=100,
    )
    query_result = execute_query(spec, data_dir=data_dir, preview_limit=100)
    ref = query_result["meta"].get("result_ref")
    if not ref:
        ref = __import__("data.result_store", fromlist=["save_result"]).save_result(query_result)

    raw = run_aggregate_data(
        input={"result_ref": ref},
        metrics=[
            {"op": "count", "field": "score", "as": "n"},
            {"op": "mean", "field": "score", "as": "avg_score"},
        ],
    )
    assert not raw.startswith("Error:")
    agg = json.loads(raw)
    validate_tabular_result(agg)
    assert len(agg["rows"]) == 1
    row = dict(zip([c["name"] for c in agg["schema"]], agg["rows"][0]))
    assert row.get("n", row.get("count_score", 0)) > 0


def test_trace_params_json_serializable():
    params = {
        "resource": "student_info",
        "select": ["student_ID"],
        "where": {"op": "eq", "field": "major", "value": "J23517"},
        "classes": ["Class1"],
        "limit": 10,
    }
    json.dumps(params)


def test_filter_tools_consult_excludes_query():
    names = {t["function"]["name"] for t in filter_tools(TOOLS, CapabilityMode.CONSULT)}
    assert "inspect_schema" in names
    assert "query_data" not in names
    assert "aggregate_data" not in names


def test_filter_tools_analyze_includes_query():
    names = {t["function"]["name"] for t in filter_tools(TOOLS, CapabilityMode.ANALYZE)}
    assert "query_data" in names
    assert "aggregate_data" in names


def test_query_submit_record_majors(data_dir, monkeypatch):
    monkeypatch.chdir(BACKEND_ROOT.parent)
    raw = run_query_data(
        resource="submit_record",
        **{"class": "Class1"},
        majors=["J23517"],
        limit=5,
        data_dir=data_dir,
    )
    assert not raw.startswith("Error:")
    result = json.loads(raw)
    assert result["meta"]["resource"] == "submit_record"
    assert result["meta"]["rows_scanned"] > 0


def test_query_submit_record_majors_smaller_than_class_only(data_dir, monkeypatch):
    monkeypatch.chdir(BACKEND_ROOT.parent)
    class_only = json.loads(
        run_query_data(resource="submit_record", **{"class": "Class1"}, limit=1, data_dir=data_dir)
    )
    filtered = json.loads(
        run_query_data(
            resource="submit_record",
            **{"class": "Class1"},
            majors=["J23517"],
            limit=1,
            data_dir=data_dir,
        )
    )
    assert class_only["meta"]["rows_scanned"] > filtered["meta"]["rows_scanned"]


def test_query_result_includes_next_step(data_dir, monkeypatch):
    monkeypatch.chdir(BACKEND_ROOT.parent)
    raw = run_query_data(
        resource="submit_record",
        **{"class": "Class1"},
        majors=["J23517"],
        select=["score"],
        data_dir=data_dir,
    )
    result = json.loads(raw)
    assert result["meta"].get("next_step", {}).get("tool") == "aggregate_data"


def test_aggregate_with_explicit_result_ref(data_dir, monkeypatch):
    monkeypatch.chdir(BACKEND_ROOT.parent)
    qraw = run_query_data(
        resource="submit_record",
        **{"class": "Class1"},
        majors=["J23517"],
        select=["score"],
        data_dir=data_dir,
    )
    q = json.loads(qraw)
    ref = q["meta"]["result_ref"]
    assert ref
    raw = run_aggregate_data(
        input={"result_ref": ref},
        metrics=[{"op": "count", "field": "score", "as": "n"}],
    )
    assert not raw.startswith("Error:")
    agg = json.loads(raw)
    assert len(agg["rows"]) == 1


def test_aggregate_missing_input_message_includes_hint():
    raw = run_aggregate_data(metrics=[{"op": "count", "field": "score", "as": "n"}])
    assert raw.startswith("Error:")
    assert "result_ref" in raw
    assert "query_data" in raw


def test_aggregate_composite_with_resource_and_filters(data_dir, monkeypatch):
    monkeypatch.chdir(BACKEND_ROOT.parent)
    raw = run_aggregate_data(
        resource="submit_record",
        **{"class": "Class1"},
        majors=["J23517"],
        metrics=[
            {"op": "count", "field": "score", "as": "n"},
            {"op": "mean", "field": "score", "as": "avg"},
        ],
        data_dir=data_dir,
    )
    assert not raw.startswith("Error:")
    agg = json.loads(raw)
    row = dict(zip([c["name"] for c in agg["schema"]], agg["rows"][0]))
    assert row.get("n", 0) > 0


def test_query_rejects_major_code_on_student_id(data_dir, monkeypatch):
    monkeypatch.chdir(BACKEND_ROOT.parent)
    raw = run_query_data(
        resource="submit_record",
        **{"class": "Class1"},
        where={"op": "eq", "field": "student_ID", "value": "J23517"},
        data_dir=data_dir,
    )
    assert raw.startswith("Error:")
    assert "major" in raw
    assert "J23517" in raw


def test_query_small_result_always_has_result_ref(data_dir, monkeypatch):
    monkeypatch.chdir(BACKEND_ROOT.parent)
    raw = run_query_data(
        resource="submit_record",
        **{"class": "Class1"},
        order_by=[{"field": "score", "dir": "asc"}],
        limit=10,
        select=["student_ID", "title_ID", "score"],
        data_dir=data_dir,
    )
    assert not raw.startswith("Error:")
    result = json.loads(raw)
    ref = result["meta"].get("result_ref")
    assert ref
    assert len(result["rows"]) == 10


def test_aggregate_on_small_query_ref_not_whole_class(data_dir, monkeypatch):
    from loop_state import AnalysisToolContext, QuerySnapshot
    from tools.runtime.data.inject import inject_data_tool_context

    monkeypatch.chdir(BACKEND_ROOT.parent)
    qraw = run_query_data(
        resource="submit_record",
        **{"class": "Class1"},
        order_by=[{"field": "score", "dir": "asc"}],
        limit=10,
        select=["score"],
        data_dir=data_dir,
    )
    q = json.loads(qraw)
    fresh_ref = q["meta"]["result_ref"]
    assert fresh_ref
    metrics = [
        {"op": "count", "field": "score", "as": "n"},
        {"op": "mean", "field": "score", "as": "avg"},
    ]
    ctx = AnalysisToolContext()
    ctx.current_user_message = "汇总这些记录的条数与均值"
    batch = [QuerySnapshot(str(fresh_ref), result_rows=10, query_limit=10)]
    args = inject_data_tool_context(
        "aggregate_data",
        {"input": {"result_ref": "query-results/stale-full-class.json"}, "metrics": metrics},
        analysis_context=ctx,
        batch_snapshots=batch,
    )
    raw = run_aggregate_data(
        input=args["input"],
        metrics=metrics,
        _ref_corrected=args.get("_ref_corrected"),
        _ref_corrected_from=args.get("_ref_corrected_from"),
        _auto_input=args.get("_auto_input"),
    )
    assert not raw.startswith("Error:")
    agg = json.loads(raw)
    assert agg["meta"].get("ref_corrected") is True
    row = dict(zip([c["name"] for c in agg["schema"]], agg["rows"][0]))
    assert row.get("n") == 10
    assert row.get("avg") == 0.0


def test_query_rejects_limit_zero(data_dir, monkeypatch):
    monkeypatch.chdir(BACKEND_ROOT.parent)
    raw = run_query_data(
        resource="student_info",
        limit=0,
        data_dir=data_dir,
    )
    assert raw.startswith("Error:")
    assert "limit" in raw.lower()
    assert "省略" in raw or "omit" in raw.lower()


def test_aggregate_count_distinct_by_major_class1(data_dir, monkeypatch):
    monkeypatch.chdir(BACKEND_ROOT.parent)
    qraw = run_query_data(
        resource="submit_record",
        **{"class": "Class1"},
        select=["major", "student_ID"],
        data_dir=data_dir,
    )
    assert not qraw.startswith("Error:")
    q = json.loads(qraw)
    ref = q["meta"]["result_ref"]
    assert ref
    raw = run_aggregate_data(
        input={"result_ref": ref},
        dimensions=["major"],
        metrics=[{"op": "count_distinct", "field": "student_ID", "as": "students"}],
    )
    assert not raw.startswith("Error:")
    agg = json.loads(raw)
    by_major = {row[0]: row[1] for row in agg["rows"]}
    assert by_major.get("J78901") == 26
    assert by_major.get("J23517") == 16
    assert sum(by_major.values()) == 96


def test_student_info_classes_emits_note(data_dir, monkeypatch):
    monkeypatch.chdir(BACKEND_ROOT.parent)
    raw = run_query_data(
        resource="student_info",
        **{"classes": ["Class1"]},
        group_by=["major"],
        data_dir=data_dir,
    )
    assert not raw.startswith("Error:")
    result = json.loads(raw)
    notes = result.get("meta", {}).get("normalization_notes") or []
    assert any("class" in n.lower() or "无 class" in n for n in notes)


def test_normalize_submit_record_joined_alias():
    resource, kwargs, notes = normalize_query_resource(
        "submit_record_joined",
        {"classes": ["Class1"]},
    )
    assert resource == "submit_record"
    assert kwargs["classes"] == ["Class1"]
    assert notes

"""Dataset lineage (parent_dataset_id) for agg → row continuity."""

from __future__ import annotations

import json
import sys
from pathlib import Path

AGENT_ROOT = Path(__file__).resolve().parents[1]
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))

import runtime_bootstrap  # noqa: F401, E402

from data.dataset_identity import describe_for_catalog  # noqa: E402
from data.dataset_registry import (  # noqa: E402
    DatasetRecord,
    append_dataset,
    build_datasets_catalog,
    format_catalog_hint,
    get_dataset_record,
)
from data.lineage import (  # noqa: E402
    format_missing_column_redirect,
    missing_fields_on_columns,
    prefer_row_parent_for_missing,
    resolve_lineage_from_input,
)
from loop_state import AnalysisToolContext  # noqa: E402
from tools.runtime.binding.context import BindingContext  # noqa: E402
from tools.runtime.binding.types import DatasetBindingDecision  # noqa: E402
from tools.runtime.binding.validate import validate_decision  # noqa: E402
from tools.runtime.data.snapshot import record_query_result  # noqa: E402


def test_resolve_lineage_from_dataset_id(tmp_path, monkeypatch):
    monkeypatch.setattr("data.dataset_registry.AGENT_STATE_DIR", tmp_path, raising=False)
    append_dataset(
        "s1",
        DatasetRecord(
            dataset_id="ds_row",
            result_ref="query-results/a.json",
            user_turn=1,
            grain="row",
            columns=["student_ID", "score", "knowledge"],
            label="原始行",
        ),
    )
    link = resolve_lineage_from_input("s1", {"dataset_id": "ds_row"})
    assert link.parent_dataset_id == "ds_row"
    assert link.parent_grain == "row"
    assert "student_ID" in (link.parent_columns or [])


def test_record_aggregate_stores_parent(tmp_path, monkeypatch):
    monkeypatch.setattr("data.dataset_registry.AGENT_STATE_DIR", tmp_path, raising=False)
    monkeypatch.setattr(
        "data.result_store.AGENT_STATE_DIR",
        tmp_path,
        raising=False,
    )
    results = tmp_path / "task_outputs" / "query-results"
    results.mkdir(parents=True)
    monkeypatch.setattr("data.result_store.QUERY_RESULTS_DIR", results, raising=False)

    append_dataset(
        "s1",
        DatasetRecord(
            dataset_id="ds_row",
            result_ref="query-results/parent.json",
            user_turn=1,
            grain="row",
            columns=["student_ID", "score", "knowledge"],
            result_rows=100,
        ),
    )
    # Full result file for row count path (not truncated)
    (results / "agg.json").write_text(
        json.dumps(
            {
                "schema": [
                    {"name": "knowledge", "type": "string"},
                    {"name": "avg", "type": "number"},
                ],
                "rows": [["k1", 1.0], ["k2", 2.0]],
                "meta": {"resource": "submit_record", "result_ref": "query-results/agg.json"},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    ctx = AnalysisToolContext(session_id="s1", user_turn=1)
    payload = json.dumps(
        {
            "schema": [
                {"name": "knowledge", "type": "string"},
                {"name": "avg", "type": "number"},
            ],
            "rows": [["k1", 1.0], ["k2", 2.0]],
            "meta": {
                "resource": "submit_record",
                "result_ref": "query-results/agg.json",
                "truncated": False,
            },
        },
        ensure_ascii=False,
    )
    out = record_query_result(
        payload,
        parsed_args={
            "dimensions": ["knowledge"],
            "metrics": [{"op": "mean", "field": "score", "as": "avg"}],
            "input": {"dataset_id": "ds_row", "result_ref": "query-results/parent.json"},
        },
        analysis_context=ctx,
        batch_snapshots=[],
        tool_name="aggregate_data",
    )
    assert out is not None
    meta = json.loads(out)["meta"]
    assert meta.get("parent_dataset_id") == "ds_row"
    assert meta.get("source_result_ref") == "query-results/parent.json"
    assert meta.get("grain") == "agg"

    rec = get_dataset_record("s1", meta["dataset_id"])
    assert rec is not None
    assert rec.parent_dataset_id == "ds_row"
    assert rec.grain == "agg"

    catalog = build_datasets_catalog("s1", tail=5)
    agg_item = next(x for x in catalog["datasets"] if x["dataset_id"] == meta["dataset_id"])
    assert agg_item["parent_dataset_id"] == "ds_row"
    hint = format_catalog_hint("s1")
    assert "parent=ds_row" in hint
    assert "parent=" in describe_for_catalog(agg_item)


def test_missing_column_redirect_points_to_parent(tmp_path, monkeypatch):
    monkeypatch.setattr("data.dataset_registry.AGENT_STATE_DIR", tmp_path, raising=False)
    append_dataset(
        "s1",
        DatasetRecord(
            dataset_id="ds_row",
            result_ref="query-results/a.json",
            user_turn=1,
            grain="row",
            columns=["student_ID", "score", "knowledge"],
        ),
    )
    append_dataset(
        "s1",
        DatasetRecord(
            dataset_id="ds_agg",
            result_ref="query-results/b.json",
            user_turn=1,
            grain="agg",
            columns=["knowledge", "avg"],
            dimensions=["knowledge"],
            parent_dataset_id="ds_row",
            source_result_ref="query-results/a.json",
            label="按knowledge汇总·无学号列",
        ),
    )
    link = prefer_row_parent_for_missing(
        "s1",
        bound_dataset_id="ds_agg",
        missing=["student_ID"],
    )
    assert link is not None
    assert link.parent_dataset_id == "ds_row"
    next_tool, example = format_missing_column_redirect(
        base_error="x",
        link=link,
        missing=["student_ID"],
    )
    assert "parent" in next_tool or "dataset_id" in next_tool
    assert "ds_row" in example
    assert "重新 query_data" in example
    assert "勿" in example


def test_binding_rejects_agg_missing_student_id(tmp_path, monkeypatch):
    monkeypatch.setattr("data.dataset_registry.AGENT_STATE_DIR", tmp_path, raising=False)
    append_dataset(
        "s1",
        DatasetRecord(
            dataset_id="ds_row",
            result_ref="query-results/a.json",
            user_turn=1,
            grain="row",
            columns=["student_ID", "score"],
            result_rows=100,
        ),
    )
    append_dataset(
        "s1",
        DatasetRecord(
            dataset_id="ds_agg",
            result_ref="query-results/b.json",
            user_turn=1,
            grain="agg",
            columns=["knowledge", "avg"],
            parent_dataset_id="ds_row",
            result_rows=8,
        ),
    )
    catalog = build_datasets_catalog("s1", tail=10)
    ctx = BindingContext(
        teacher_message="按学生找最低分",
        current_user_turn=1,
        session_id="s1",
        candidates=[],
        query_summaries=[],
        catalog_datasets=list(catalog["datasets"]),
        model_input={"dataset_id": "ds_agg"},
        model_metrics=[{"op": "mean", "field": "score", "as": "avg"}],
        model_bind=None,
        model_dimensions=["student_ID"],
    )
    err = validate_decision(
        DatasetBindingDecision(
            scope="explicit_dataset",
            dataset_id="ds_agg",
            result_ref="query-results/b.json",
        ),
        ctx,
    )
    assert err is not None
    assert "ds_row" in err
    assert "student_ID" in err or "缺少列" in err
    assert "query_data" in err  # mentions 勿重新 query_data


def test_missing_fields_helper():
    assert missing_fields_on_columns(
        ["knowledge", "avg"],
        [{"op": "mean", "field": "score"}],
        ["student_ID"],
    ) == ["score", "student_ID"]
    assert missing_fields_on_columns(["student_ID", "score"], [{"op": "mean", "field": "score"}], ["student_ID"]) == []


def test_schema_payload_registers_columns(tmp_path, monkeypatch):
    """Production tabular shape uses schema[], not top-level columns."""
    monkeypatch.setattr("data.dataset_registry.AGENT_STATE_DIR", tmp_path, raising=False)
    results = tmp_path / "task_outputs" / "query-results"
    results.mkdir(parents=True)
    monkeypatch.setattr("data.result_store.QUERY_RESULTS_DIR", results, raising=False)
    (results / "agg.json").write_text(
        json.dumps(
            {
                "schema": [
                    {"name": "knowledge", "type": "string"},
                    {"name": "avg", "type": "number"},
                ],
                "rows": [["k1", 1.0]],
                "meta": {"resource": "submit_record", "result_ref": "query-results/agg.json"},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    append_dataset(
        "s1",
        DatasetRecord(
            dataset_id="ds_row",
            result_ref="query-results/parent.json",
            user_turn=1,
            grain="row",
            columns=["student_ID", "score", "knowledge"],
            result_rows=100,
        ),
    )
    ctx = AnalysisToolContext(session_id="s1", user_turn=1)
    out = record_query_result(
        json.dumps(
            {
                "schema": [
                    {"name": "knowledge", "type": "string"},
                    {"name": "avg", "type": "number"},
                ],
                "rows": [["k1", 1.0]],
                "meta": {
                    "resource": "submit_record",
                    "result_ref": "query-results/agg.json",
                    "truncated": False,
                },
            },
            ensure_ascii=False,
        ),
        parsed_args={
            "dimensions": ["knowledge"],
            "metrics": [{"op": "mean", "field": "score", "as": "avg"}],
            "input": {"dataset_id": "ds_row"},
        },
        analysis_context=ctx,
        batch_snapshots=[],
        tool_name="aggregate_data",
    )
    meta = json.loads(out)["meta"]
    assert meta["columns"] == ["knowledge", "avg"]
    rec = get_dataset_record("s1", meta["dataset_id"])
    assert rec is not None
    assert rec.columns == ["knowledge", "avg"]


def test_walk_parent_chain_skips_mid_agg(tmp_path, monkeypatch):
    monkeypatch.setattr("data.dataset_registry.AGENT_STATE_DIR", tmp_path, raising=False)
    append_dataset(
        "s1",
        DatasetRecord(
            dataset_id="ds_row",
            result_ref="query-results/a.json",
            user_turn=1,
            grain="row",
            columns=["student_ID", "score", "knowledge"],
        ),
    )
    append_dataset(
        "s1",
        DatasetRecord(
            dataset_id="ds_mid",
            result_ref="query-results/b.json",
            user_turn=1,
            grain="agg",
            columns=["knowledge", "n"],
            parent_dataset_id="ds_row",
        ),
    )
    append_dataset(
        "s1",
        DatasetRecord(
            dataset_id="ds_top",
            result_ref="query-results/c.json",
            user_turn=1,
            grain="agg",
            columns=["week_index", "n"],
            parent_dataset_id="ds_mid",
        ),
    )
    from data.lineage import walk_parent_chain_for_columns

    link = walk_parent_chain_for_columns("s1", "ds_mid", ["student_ID"])
    assert link is not None
    assert link.parent_dataset_id == "ds_row"
    link2 = prefer_row_parent_for_missing(
        "s1", bound_dataset_id="ds_top", missing=["student_ID"]
    )
    assert link2 is not None
    assert link2.parent_dataset_id == "ds_row"


def test_single_candidate_binding_rejects_agg_missing_cols(tmp_path, monkeypatch):
    monkeypatch.setattr("data.dataset_registry.AGENT_STATE_DIR", tmp_path, raising=False)
    append_dataset(
        "s1",
        DatasetRecord(
            dataset_id="ds_row",
            result_ref="query-results/a.json",
            user_turn=1,
            grain="row",
            columns=["student_ID", "score"],
            result_rows=100,
        ),
    )
    append_dataset(
        "s1",
        DatasetRecord(
            dataset_id="ds_agg",
            result_ref="query-results/b.json",
            user_turn=1,
            grain="agg",
            columns=["knowledge", "avg"],
            parent_dataset_id="ds_row",
            result_rows=8,
        ),
    )
    from loop_state import QuerySnapshot
    from tools.runtime.binding.pipeline import resolve_aggregate_binding
    from tools.runtime.binding.types import BindMode

    ctx = AnalysisToolContext(session_id="s1", user_turn=1)
    ctx.turn_snapshots = [
        QuerySnapshot(
            result_ref="query-results/b.json",
            result_rows=8,
            dataset_id="ds_agg",
            resource="submit_record",
        )
    ]
    binding = resolve_aggregate_binding(
        {},
        metrics=[{"op": "mean", "field": "score", "as": "avg"}],
        dimensions=["student_ID"],
        bind=BindMode.AUTO,
        analysis_context=ctx,
        batch_snapshots=[],
    )
    assert binding.error
    assert "ds_row" in (binding.error or "")
    assert binding.result_ref is None

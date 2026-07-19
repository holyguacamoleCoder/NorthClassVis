"""Dataset identity (grain/label) for unambiguous 指代."""

from __future__ import annotations

import sys
from pathlib import Path

AGENT_ROOT = Path(__file__).resolve().parents[1]
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))

import runtime_bootstrap  # noqa: F401, E402

from data.dataset_identity import (  # noqa: E402
    build_dataset_label,
    column_names_from_payload,
    describe_for_catalog,
    infer_grain,
)
from data.dataset_registry import DatasetRecord, append_dataset, format_catalog_hint  # noqa: E402


def test_column_names_from_schema_payload():
    cols = column_names_from_payload(
        {
            "schema": [
                {"name": "knowledge", "type": "string"},
                {"name": "平均分", "type": "number"},
            ],
            "rows": [["k1", 1.0]],
        }
    )
    assert cols == ["knowledge", "平均分"]


def test_infer_grain_aggregate_vs_query():
    assert infer_grain(tool_name="aggregate_data") == "agg"
    assert infer_grain(tool_name="query_data") == "row"
    assert (
        infer_grain(parsed_args={"dimensions": ["knowledge"], "metrics": [{"op": "count"}]})
        == "agg"
    )


def test_label_distinguishes_row_and_knowledge_agg():
    row = build_dataset_label(
        grain="row",
        resource="submit_record",
        classes=["Class2"],
        parsed_args={
            "where": {
                "op": "and",
                "conditions": [
                    {"field": "week_index", "op": "gte", "value": 13},
                    {"field": "week_index", "op": "lte", "value": 15},
                ],
            }
        },
        columns=["student_ID", "score", "title_ID"],
        result_rows=1826,
        query_limit=None,
    )
    assert "原始行" in row
    assert "Class2" in row
    assert "周13-15" in row
    assert "student" not in row.lower() or "原始行" in row

    agg = build_dataset_label(
        grain="agg",
        resource="submit_record",
        classes=["Class2"],
        dimensions=["knowledge"],
        columns=["knowledge", "总提交次数", "平均分"],
        result_rows=8,
    )
    assert "按knowledge汇总" in agg
    assert "无学号列" in agg
    assert "原始行" not in agg


def test_catalog_hint_shows_grain_and_label(tmp_path, monkeypatch):
    monkeypatch.setattr("data.dataset_registry.AGENT_STATE_DIR", tmp_path, raising=False)
    append_dataset(
        "sess-id",
        DatasetRecord(
            dataset_id="ds_row",
            result_ref="query-results/a.json",
            user_turn=1,
            resource="submit_record",
            result_rows=1826,
            grain="row",
            label="Class2·周13-15·submit_record·原始行·全量·1826行",
            columns=["student_ID", "score"],
        ),
    )
    append_dataset(
        "sess-id",
        DatasetRecord(
            dataset_id="ds_agg",
            result_ref="query-results/b.json",
            user_turn=1,
            resource="submit_record",
            result_rows=8,
            grain="agg",
            label="Class2·submit_record·按knowledge汇总·无学号列·8行",
            columns=["knowledge", "平均分"],
            dimensions=["knowledge"],
        ),
    )
    hint = format_catalog_hint("sess-id", tail=5)
    assert "grain=row" in hint
    assert "grain=agg" in hint
    assert "原始行" in hint
    assert "按knowledge汇总" in hint
    assert "无学号列" in hint
    assert describe_for_catalog(
        {"dataset_id": "ds_agg", "grain": "agg", "label": "x", "columns": ["knowledge"]}
    ).startswith("ds_agg")

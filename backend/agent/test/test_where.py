"""Tests for query_data where DSL (and composite, week field aliases)."""

import importlib.util
import json
from pathlib import Path

import pandas as pd
import pytest

import runtime_bootstrap  # noqa: F401, E402

BACKEND_ROOT = Path(__file__).resolve().parents[2]

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("numpy") is None,
    reason="numpy 未安装",
)
pytest.importorskip("pandas")

from data.exceptions import InvalidParameterError  # noqa: E402
from data.where import apply_where, normalize_where, repair_where  # noqa: E402
from tools.handlers.data_tools import run_query_data  # noqa: E402


@pytest.fixture
def data_dir():
    return BACKEND_ROOT.parent / "data"


def test_where_and_composite_on_dataframe():
    df = pd.DataFrame({"week_index": [12, 13, 14, 15, 16], "peak_value": [0.1, 0.2, 0.3, 0.4, 0.5]})
    where = {
        "op": "and",
        "conditions": [
            {"field": "week_index", "op": "gte", "value": 13},
            {"field": "week_index", "op": "lte", "value": 15},
        ],
    }
    out, notes = apply_where(df, where, ["week_index", "peak_value"], resource="week_aggregation")
    assert list(out["week_index"]) == [13, 14, 15]
    assert notes == []


def test_normalize_week_alias_for_week_aggregation():
    where = {"op": "gte", "field": "week", "value": 13}
    norm, notes = normalize_where(
        where,
        resource="week_aggregation",
        allowed_columns=["student_ID", "week_index", "peak_value", "direction"],
    )
    assert norm is not None
    assert norm["field"] == "week_index"
    assert any("week_index" in n for n in notes)


def test_week_on_submit_record_raises_actionable_error():
    where = {
        "op": "and",
        "conditions": [
            {"field": "week", "op": "gte", "value": 13},
            {"field": "week", "op": "lte", "value": 15},
        ],
    }
    allowed = [
        "index",
        "class",
        "time",
        "state",
        "score",
        "title_ID",
        "method",
        "memory",
        "timeconsume",
        "student_ID",
        "knowledge",
        "sub_knowledge",
        "major",
        "sex",
        "age",
    ]
    with pytest.raises(InvalidParameterError) as exc_info:
        normalize_where(where, resource="submit_record", allowed_columns=allowed)
    assert "week_aggregation" in str(exc_info.value)
    assert exc_info.value.param == "where"


def test_query_week_and_on_week_aggregation(data_dir, monkeypatch):
    monkeypatch.chdir(BACKEND_ROOT.parent)
    raw = run_query_data(
        resource="week_aggregation",
        classes=["Class2"],
        where={
            "op": "and",
            "conditions": [
                {"field": "week", "op": "gte", "value": 13},
                {"field": "week", "op": "lte", "value": 15},
            ],
        },
        data_dir=data_dir,
    )
    assert not raw.startswith("Error:"), raw
    payload = json.loads(raw)
    weeks = {row[1] for row in payload["rows"] if len(row) > 1}
    assert weeks.issubset({13, 14, 15})
    notes = payload.get("meta", {}).get("normalization_notes") or []
    assert any("week_index" in n for n in notes)


def test_repair_missing_op_defaults_to_eq():
    fixed, notes = repair_where({"field": "student_ID", "value": "abc123"})
    assert fixed == {"op": "eq", "field": "student_ID", "value": "abc123"}
    assert any("eq" in n for n in notes)


def test_repair_operator_alias():
    fixed, _ = repair_where({"field": "major", "operator": "eq", "value": "J23517"})
    assert fixed["op"] == "eq"


def test_repair_between_expands_to_and():
    fixed, notes = repair_where(
        {"field": "week_index", "op": "between", "value": [13, 15]}
    )
    assert fixed["op"] == "and"
    assert len(fixed["conditions"]) == 2
    assert any("between" in n for n in notes)


def test_repair_where_array():
    fixed, notes = repair_where(
        [
            {"field": "week_index", "op": "gte", "value": 13},
            {"field": "week_index", "op": "lte", "value": 15},
        ]
    )
    assert fixed["op"] == "and"
    assert len(fixed["conditions"]) == 2
    assert any("数组" in n for n in notes)


def test_query_missing_op_repaired(data_dir, monkeypatch):
    monkeypatch.chdir(BACKEND_ROOT.parent)
    raw = run_query_data(
        resource="week_aggregation",
        classes=["Class2"],
        where={"field": "week_index", "value": 14},
        limit=5,
        data_dir=data_dir,
    )
    assert not raw.startswith("Error:"), raw
    payload = json.loads(raw)
    notes = payload.get("meta", {}).get("normalization_notes") or []
    assert any("eq" in n for n in notes)


def test_query_week_on_submit_record(data_dir, monkeypatch):
    monkeypatch.chdir(BACKEND_ROOT.parent)
    raw = run_query_data(
        resource="submit_record",
        classes=["Class2"],
        where={"field": "week", "op": "gte", "value": 13},
        limit=10,
        data_dir=data_dir,
    )
    assert not raw.startswith("Error:"), raw
    payload = json.loads(raw)
    notes = payload.get("meta", {}).get("normalization_notes") or []
    assert any("week_index" in n for n in notes)

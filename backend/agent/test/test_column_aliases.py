"""Tests for column alias normalization in aggregate_data."""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

import runtime_bootstrap  # noqa: F401, E402

BACKEND_ROOT = Path(__file__).resolve().parents[2]

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("numpy") is None,
    reason="numpy 未安装",
)
pytest.importorskip("pandas")

from data.column_aliases import resolve_column, resolve_columns  # noqa: E402
from data.query import QuerySpec, execute_query  # noqa: E402
from tools.handlers.data_tools import run_aggregate_data, run_query_data  # noqa: E402


@pytest.fixture
def data_dir():
    return BACKEND_ROOT.parent / "data"


def test_resolve_week_alias():
    available = ["student_ID", "week_index", "peak_value", "direction"]
    assert resolve_column("week", available) == "week_index"
    assert resolve_column("weekIndex", available) == "week_index"
    assert resolve_column("Week", available) == "week_index"
    resolved, missing, notes = resolve_columns(["week"], available)
    assert resolved == ["week_index"]
    assert not missing
    assert notes


def test_resolve_camel_case_id_columns():
    available = ["student_ID", "title_ID", "score"]
    assert resolve_column("studentId", available) == "student_ID"
    assert resolve_column("student_id", available) == "student_ID"
    assert resolve_column("titleId", available) == "title_ID"


def test_aggregate_week_alias_on_week_aggregation(data_dir, monkeypatch):
    monkeypatch.chdir(BACKEND_ROOT.parent)
    spec = QuerySpec(
        resource="week_aggregation",
        resolve_params={"classes": ["Class1"], "week_range": [0, 15]},
    )
    query_result = execute_query(spec, data_dir=data_dir, preview_limit=50)
    ref = query_result["meta"]["result_ref"]
    assert ref

    raw = run_aggregate_data(
        input={"result_ref": ref},
        dimensions=["week"],
        metrics=[{"op": "mean", "field": "peak_value", "as": "avg_peak"}],
    )
    assert not raw.startswith("Error:"), raw
    agg = json.loads(raw)
    assert len(agg["rows"]) > 0


def test_aggregate_score_on_wrong_resource_shows_hint(data_dir, monkeypatch):
    monkeypatch.chdir(BACKEND_ROOT.parent)
    spec = QuerySpec(
        resource="week_aggregation",
        resolve_params={"classes": ["Class1"]},
    )
    query_result = execute_query(spec, data_dir=data_dir, preview_limit=50)
    ref = query_result["meta"]["result_ref"]

    raw = run_aggregate_data(
        input={"result_ref": ref},
        metrics=[{"op": "mean", "field": "score", "as": "avg"}],
    )
    assert raw.startswith("Error:")
    assert "score" in raw
    assert "submit_record" in raw or "week_aggregation" in raw


def test_query_limit_zero_normalized(data_dir, monkeypatch):
    monkeypatch.chdir(BACKEND_ROOT.parent)
    raw = run_query_data(
        resource="student_info",
        limit=0,
        data_dir=data_dir,
    )
    assert not raw.startswith("Error:"), raw
    payload = json.loads(raw)
    notes = payload.get("meta", {}).get("normalization_notes") or payload.get("normalization_notes") or []
    assert any("limit=0" in n for n in notes) or payload["meta"].get("rows_scanned", 0) > 0

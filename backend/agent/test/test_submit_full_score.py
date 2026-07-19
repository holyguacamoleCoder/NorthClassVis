"""submit_record exposes title full_score via left join (no hand-crafted join)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

AGENT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = AGENT_ROOT.parent
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))

import runtime_bootstrap  # noqa: F401, E402

pytest.importorskip("pandas")

from data.derived import build_submit_record_joined  # noqa: E402
from data.registry import _load_registry_document  # noqa: E402
from tools.handlers.data_tools import run_aggregate_data, run_inspect_schema, run_query_data  # noqa: E402


@pytest.fixture
def data_dir():
    return BACKEND_ROOT.parent / "data"


def test_build_submit_record_joined_has_full_score(data_dir, monkeypatch):
    monkeypatch.chdir(BACKEND_ROOT.parent)
    _load_registry_document.cache_clear()
    df = build_submit_record_joined(["Class1"], data_dir=data_dir)
    assert not df.empty
    assert "full_score" in df.columns
    assert "score_rate" in df.columns
    assert "score" in df.columns
    # Full scores should be positive for known titles
    assert float(df["full_score"].dropna().min()) > 0
    # score_rate in [0, 1] when defined
    rates = df["score_rate"].dropna()
    assert (rates >= 0).all()
    assert (rates <= 1.01).all()  # tiny float slack


def test_inspect_and_query_expose_full_score(data_dir, monkeypatch):
    monkeypatch.chdir(BACKEND_ROOT.parent)
    _load_registry_document.cache_clear()
    raw = run_inspect_schema(resource="submit_record", **{"class": "Class1"}, data_dir=data_dir)
    payload = json.loads(raw)
    names = {c["name"] for c in payload["columns"]}
    assert "full_score" in names
    assert "score_rate" in names

    q = run_query_data(
        resource="submit_record",
        **{"class": "Class1"},
        select=["student_ID", "title_ID", "score", "full_score", "score_rate"],
        limit=20,
        data_dir=data_dir,
    )
    assert not q.startswith("Error:")
    result = json.loads(q)
    schema_names = [c["name"] for c in result["schema"]]
    assert "full_score" in schema_names
    assert "score_rate" in schema_names
    hint = " ".join((result.get("meta") or {}).get("warnings") or []) + str(
        (result.get("meta") or {}).get("metric_hint") or ""
    )
    assert "full_score" in hint


def test_aggregate_accuracy_from_full_score(data_dir, monkeypatch, tmp_path):
    monkeypatch.chdir(BACKEND_ROOT.parent)
    _load_registry_document.cache_clear()
    monkeypatch.setenv("AGENT_STATE_DIR", str(tmp_path))
    # Force result store into tmp if needed — query still works via default paths
    q = run_query_data(
        resource="submit_record",
        **{"class": "Class1"},
        where={
            "op": "and",
            "conditions": [
                {"field": "week_index", "op": "gte", "value": 1},
                {"field": "week_index", "op": "lte", "value": 5},
            ],
        },
        data_dir=data_dir,
    )
    assert not q.startswith("Error:")
    meta = json.loads(q)["meta"]
    ref = meta["result_ref"]
    ds = meta.get("dataset_id")

    agg = run_aggregate_data(
        input={"result_ref": ref, **({"dataset_id": ds} if ds else {})},
        dimensions=["student_ID"],
        metrics=[
            {"op": "sum", "field": "score", "as": "total_earned"},
            {"op": "sum", "field": "full_score", "as": "total_possible"},
            {"op": "mean", "field": "score_rate", "as": "avg_rate"},
            {"op": "count", "as": "n"},
        ],
        order_by=[{"field": "avg_rate", "dir": "asc"}],
        limit=5,
        data_dir=data_dir,
    )
    assert not agg.startswith("Error:"), agg
    out = json.loads(agg)
    schema = [c["name"] for c in out["schema"]]
    assert "total_earned" in schema
    assert "total_possible" in schema
    assert "avg_rate" in schema
    assert len(out["rows"]) <= 5

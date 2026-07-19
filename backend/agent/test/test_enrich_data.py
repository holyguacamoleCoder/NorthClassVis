"""enrich_data: generic left-join lookup onto a prior dataset."""

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

from data.enrich import EnrichSpec, execute_enrich  # noqa: E402
from data.query import QuerySpec, execute_query  # noqa: E402
from data.registry import _load_registry_document  # noqa: E402
from tools.definitions.manifest import MANIFEST_BY_NAME  # noqa: E402
from tools.handlers.data_tools import run_enrich_data, run_query_data  # noqa: E402
from tools.runtime.data.ordering import partition_tool_calls_for_data_pipeline  # noqa: E402


@pytest.fixture
def data_dir():
    return BACKEND_ROOT.parent / "data"


def test_enrich_tool_registered():
    assert "enrich_data" in MANIFEST_BY_NAME


def test_partition_enrich_between_query_and_aggregate():
    calls = [
        {"name": "aggregate_data", "id": "a"},
        {"name": "enrich_data", "id": "e"},
        {"name": "query_data", "id": "q"},
    ]
    queries, rest = partition_tool_calls_for_data_pipeline(calls)
    assert [c["id"] for c in queries] == ["q"]
    assert [c["id"] for c in rest] == ["e", "a"]


def test_execute_enrich_title_full_score(data_dir, monkeypatch, tmp_path):
    monkeypatch.chdir(BACKEND_ROOT.parent)
    _load_registry_document.cache_clear()
    monkeypatch.setattr("data.result_store.AGENT_STATE_DIR", tmp_path, raising=False)
    monkeypatch.setattr(
        "data.result_store.QUERY_RESULTS_DIR",
        tmp_path / "task_outputs" / "query-results",
        raising=False,
    )

    # Build a minimal left table without full_score (simulate raw slice)
    left = execute_query(
        QuerySpec(
            resource="submit_record",
            resolve_params={"class": "Class1"},
            select=["student_ID", "title_ID", "score"],
            limit=30,
        ),
        data_dir=data_dir,
        preview_limit=50,
    )
    # Drop full_score/score_rate if loader already attached them — re-save narrow
    import pandas as pd
    from data.aggregate import _tabular_to_dataframe
    from data.result_store import save_result
    from data.tabular import dataframe_to_tabular

    df, _ = _tabular_to_dataframe(left)
    narrow = df[["student_ID", "title_ID", "score"]].copy()
    payload = dataframe_to_tabular(narrow, "submit_record_narrow")
    ref = save_result(payload)

    out = execute_enrich(
        EnrichSpec(
            input={"result_ref": ref},
            lookup="title_info",
            on="title_ID",
            columns=["score"],
            rename={"score": "full_score"},
            compute_score_rate=True,
        ),
        data_dir=data_dir,
    )
    names = [c["name"] for c in out["schema"]]
    assert "full_score" in names
    assert "score_rate" in names
    assert "score" in names
    meta = out["meta"]["enrich"]
    assert meta["lookup"] == "title_info"
    assert meta["how"] == "left"
    assert "full_score" in meta["columns_added"]


def test_run_enrich_data_handler(data_dir, monkeypatch, tmp_path):
    monkeypatch.chdir(BACKEND_ROOT.parent)
    _load_registry_document.cache_clear()
    monkeypatch.setattr("data.result_store.AGENT_STATE_DIR", tmp_path, raising=False)
    monkeypatch.setattr(
        "data.result_store.QUERY_RESULTS_DIR",
        tmp_path / "task_outputs" / "query-results",
        raising=False,
    )

    q = run_query_data(
        resource="submit_record",
        **{"class": "Class1"},
        select=["student_ID", "title_ID", "score"],
        limit=15,
        data_dir=data_dir,
    )
    assert not q.startswith("Error:")
    ref = json.loads(q)["meta"]["result_ref"]

    raw = run_enrich_data(
        input={"result_ref": ref},
        lookup="title_info",
        on="title_ID",
        columns=["score", "knowledge"],
        rename={"score": "full_score"},
        compute_score_rate=True,
        data_dir=data_dir,
    )
    assert not raw.startswith("Error:"), raw
    payload = json.loads(raw)
    names = [c["name"] for c in payload["schema"]]
    assert "full_score" in names
    assert payload["meta"].get("grain") == "row"

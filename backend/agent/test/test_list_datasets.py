"""Tests for list_datasets tool and catalog builder."""

import json
import sys
from pathlib import Path

AGENT_ROOT = Path(__file__).resolve().parents[1]
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))

import runtime_bootstrap  # noqa: F401, E402

from data.dataset_registry import (  # noqa: E402
    DatasetRecord,
    append_dataset,
    build_datasets_catalog,
)
from loop_state import AnalysisToolContext  # noqa: E402
from tools.handlers.data_tools import run_list_datasets  # noqa: E402
from tools.runtime.data_chain import inject_data_tool_context  # noqa: E402


def test_build_catalog_newest_first_and_current_turn_flag():
    sid = "sess-catalog"
    append_dataset(
        sid,
        DatasetRecord(
            dataset_id="ds_old",
            result_ref="query-results/old.json",
            user_turn=1,
            result_rows=10,
            query_limit=10,
        ),
    )
    append_dataset(
        sid,
        DatasetRecord(
            dataset_id="ds_new",
            result_ref="query-results/new.json",
            user_turn=2,
            result_rows=22960,
            resource="submit_record",
        ),
    )
    payload = build_datasets_catalog(sid, tail=10, current_user_turn=2)
    ids = [d["dataset_id"] for d in payload["datasets"]]
    assert ids[0] == "ds_new"
    assert payload["datasets"][0]["is_current_turn"] is True
    assert payload["datasets"][1]["is_current_turn"] is False


def test_run_list_datasets_requires_session():
    raw = run_list_datasets()
    assert raw.startswith("Error:")


def test_run_list_datasets_returns_entries():
    sid = "sess-run-unique-x"
    append_dataset(
        sid,
        DatasetRecord(
            dataset_id="ds_x",
            result_ref="query-results/x.json",
            user_turn=1,
            result_rows=5,
            query_limit=5,
        ),
    )
    raw = run_list_datasets(_session_id=sid, _current_user_turn=1, tail=10)
    data = json.loads(raw)
    assert len(data["datasets"]) == 1
    assert data["datasets"][0]["dataset_id"] == "ds_x"
    assert data["meta"]["next_step"]["tool"] == "aggregate_data"


def test_inject_passes_session_for_list_datasets():
    ctx = AnalysisToolContext(session_id="sess-inject", user_turn=3)
    args = inject_data_tool_context(
        "list_datasets",
        {"tail": 5},
        analysis_context=ctx,
        batch_snapshots=[],
    )
    assert args["_session_id"] == "sess-inject"
    assert args["_current_user_turn"] == 3

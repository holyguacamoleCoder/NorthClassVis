"""Tests for query → aggregate dataset binding."""

import importlib.util
import sys
from pathlib import Path

import pytest

import runtime_bootstrap  # noqa: F401, E402

AGENT_ROOT = Path(__file__).resolve().parents[1]
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))

from data.dataset_registry import append_dataset, DatasetRecord  # noqa: E402
from loop_state import AnalysisToolContext, QuerySnapshot  # noqa: E402
from tools.runtime.binding.types import BindMode  # noqa: E402
from tools.runtime.binding.scoring import pick_best_candidate  # noqa: E402
from tools.runtime.binding.context import _snap_to_candidate  # noqa: E402
from tools.runtime.data.inject import inject_data_tool_context  # noqa: E402
from tools.runtime.data.ordering import partition_tool_calls_for_data_pipeline  # noqa: E402
from tools.runtime.binding.pipeline import resolve_aggregate_binding  # noqa: E402

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("numpy") is None,
    reason="numpy 未安装",
)


def test_partition_runs_queries_first():
    calls = [
        {"name": "aggregate_data", "id": "a"},
        {"name": "query_data", "id": "q"},
        {"name": "read_file", "id": "r"},
    ]
    queries, rest = partition_tool_calls_for_data_pipeline(calls)
    assert [c["id"] for c in queries] == ["q"]
    assert [c["id"] for c in rest] == ["a", "r"]


def test_inject_aggregate_prefers_batch_last_over_stale():
    ctx = AnalysisToolContext()
    ctx.working_active_ref = "query-results/stale-limit.json"
    batch = [QuerySnapshot("query-results/full.json", result_rows=22960)]
    args = inject_data_tool_context(
        "aggregate_data",
        {
            "input": {"result_ref": "query-results/stale-limit.json"},
            "metrics": [{"op": "count", "as": "n"}],
        },
        analysis_context=ctx,
        batch_snapshots=batch,
    )
    assert args["input"]["result_ref"] == "query-results/full.json"
    assert args.get("_ref_corrected") is True


def test_inject_aggregate_uses_turn_snapshot_when_no_batch():
    ctx = AnalysisToolContext()
    ctx.register_query_snapshot(
        QuerySnapshot("query-results/latest.json", result_rows=100)
    )
    args = inject_data_tool_context(
        "aggregate_data",
        {"metrics": [{"op": "count", "as": "n"}]},
        analysis_context=ctx,
        batch_snapshots=[],
    )
    assert args["input"]["result_ref"] == "query-results/latest.json"
    assert args.get("_auto_input") is True


def test_cross_turn_ref_rejected_without_dataset_id():
    ctx = AnalysisToolContext(session_id="sess-test", user_turn=2)
    append_dataset(
        "sess-test",
        DatasetRecord(
            dataset_id="ds_old",
            result_ref="query-results/old-turn.json",
            user_turn=1,
            result_rows=10,
            query_limit=10,
        ),
    )
    binding = resolve_aggregate_binding(
        {"result_ref": "query-results/old-turn.json"},
        metrics=[{"op": "count", "as": "n"}],
        dimensions=None,
        bind=BindMode.AUTO,
        analysis_context=ctx,
        batch_snapshots=[],
    )
    assert binding.error
    assert "上一轮" in binding.error


def test_cross_turn_allowed_with_dataset_id():
    ctx = AnalysisToolContext(session_id="sess-test2", user_turn=2)
    append_dataset(
        "sess-test2",
        DatasetRecord(
            dataset_id="ds_keep",
            result_ref="query-results/prior.json",
            user_turn=1,
            result_rows=10,
            query_limit=10,
        ),
    )
    binding = resolve_aggregate_binding(
        {"dataset_id": "ds_keep"},
        metrics=[{"op": "mean", "field": "score", "as": "avg"}],
        dimensions=None,
        bind=BindMode.CHAIN,
        analysis_context=ctx,
        batch_snapshots=[],
    )
    assert binding.error is None
    assert binding.result_ref == "query-results/prior.json"


def test_pick_fresh_prefers_full_scan():
    ctx_turn = 1
    candidates = [
        QuerySnapshot("query-results/slice.json", result_rows=10, query_limit=10),
        QuerySnapshot("query-results/full.json", result_rows=22960),
    ]
    cands = [_snap_to_candidate(s, ctx_turn) for s in candidates]
    best = pick_best_candidate(
        cands,
        metrics=[{"op": "count_distinct", "field": "student_ID", "as": "n"}],
        dimensions=None,
        bind=BindMode.FRESH,
        current_user_turn=1,
    )
    assert best is not None
    assert best.result_ref.endswith("full.json")


def test_inject_binding_error_when_no_turn_data():
    ctx = AnalysisToolContext()
    ctx.begin_user_turn()
    args = inject_data_tool_context(
        "aggregate_data",
        {"metrics": [{"op": "count", "as": "n"}]},
        analysis_context=ctx,
        batch_snapshots=[],
    )
    assert args.get("_binding_error")

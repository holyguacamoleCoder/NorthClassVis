"""BindingCandidate slice vs broad heuristics (no magic row-count thresholds)."""

import sys
from pathlib import Path

import runtime_bootstrap  # noqa: F401, E402

AGENT_ROOT = Path(__file__).resolve().parents[1]
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))

from tools.runtime.binding.types import BindingCandidate  # noqa: E402


def test_week_aggregation_full_class_scan_is_broad_not_slice():
    """~students×weeks rows (e.g. 255) must not be rejected as class_wide slice."""
    cand = BindingCandidate(
        result_ref="query-results/week.json",
        result_rows=255,
        user_turn=1,
        query_limit=None,
        rows_scanned=255,
        resource="week_aggregation",
    )
    assert not cand.is_slice
    assert cand.is_broad_scan


def test_preview_truncation_is_slice():
    cand = BindingCandidate(
        result_ref="query-results/preview.json",
        result_rows=50,
        user_turn=1,
        query_limit=None,
        rows_scanned=22960,
        resource="submit_record",
    )
    assert cand.is_slice
    assert not cand.is_broad_scan


def test_explicit_limit_is_slice():
    cand = BindingCandidate(
        result_ref="query-results/top10.json",
        result_rows=10,
        user_turn=1,
        query_limit=10,
        rows_scanned=22960,
        resource="submit_record",
    )
    assert cand.is_slice
    assert not cand.is_broad_scan


def test_submit_record_full_scan_is_broad():
    cand = BindingCandidate(
        result_ref="query-results/full.json",
        result_rows=13845,
        user_turn=1,
        query_limit=None,
        rows_scanned=13845,
        resource="submit_record",
    )
    assert not cand.is_slice
    assert cand.is_broad_scan


def test_validate_class_wide_accepts_week_aggregation_255_rows():
    from tools.runtime.binding.context import build_binding_context
    from tools.runtime.binding.types import DatasetBindingDecision
    from tools.runtime.binding.validate import validate_decision
    from loop_state import AnalysisToolContext, QuerySnapshot

    ctx = AnalysisToolContext(session_id="t", user_turn=1)
    ctx.current_user_message = "Class2 第 13-15 周班级整体趋势"
    snap = QuerySnapshot(
        "query-results/week.json",
        result_rows=255,
        query_limit=None,
        rows_scanned=255,
        dataset_id="ds_week",
        resource="week_aggregation",
    )
    ctx.register_query_snapshot(snap)
    bctx = build_binding_context(
        inp={},
        metrics=[{"op": "mean", "field": "peak_value", "as": "avg"}],
        dimensions=None,
        bind="auto",
        analysis_context=ctx,
        batch_snapshots=[snap],
    )
    decision = DatasetBindingDecision(
        scope="class_wide",
        dataset_id="ds_week",
        result_ref="query-results/week.json",
        resolver="rule",
    )
    assert validate_decision(decision, bctx) is None

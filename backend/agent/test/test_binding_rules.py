"""Tests for hard aggregate binding rules (cross-turn / chain_slice)."""

import os
import sys
from pathlib import Path

AGENT_ROOT = Path(__file__).resolve().parents[1]
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))

import runtime_bootstrap  # noqa: F401, E402

os.environ["BINDING_RESOLVER_DISABLE_LLM"] = "1"

from data.dataset_registry import DatasetRecord, append_dataset  # noqa: E402
from loop_state import AnalysisToolContext, QuerySnapshot  # noqa: E402
from tools.runtime.binding.pipeline import resolve_aggregate_binding  # noqa: E402
from tools.runtime.binding.types import BindMode  # noqa: E402
from tools.runtime.binding.validate import validate_decision  # noqa: E402
from tools.runtime.binding.context import build_binding_context  # noqa: E402
from tools.runtime.binding.types import DatasetBindingDecision  # noqa: E402


def _ctx(msg: str, *, session_id: str = "rule-test", user_turn: int = 1) -> AnalysisToolContext:
    c = AnalysisToolContext(session_id=session_id, user_turn=user_turn)
    c.current_user_message = msg
    return c


def test_silent_cross_turn_rejects_without_dataset_id():
    sid = "silent-cross-turn"
    append_dataset(
        sid,
        DatasetRecord(
            dataset_id="ds_old",
            result_ref="query-results/prior.json",
            user_turn=1,
            result_rows=10,
            query_limit=10,
        ),
    )
    ctx = _ctx("直接 aggregate 均值，不要新 query，也不要传 dataset_id", session_id=sid, user_turn=2)
    binding = resolve_aggregate_binding(
        {},
        metrics=[{"op": "mean", "field": "score", "as": "avg"}],
        dimensions=None,
        bind=BindMode.AUTO,
        analysis_context=ctx,
        batch_snapshots=[],
    )
    assert binding.error
    assert "上一轮" in binding.error
    assert binding.trace.get("resolver") == "silent_cross_turn_reject"


def test_rule_chain_slice_corrects_broad_ref():
    ctx = _ctx("汇总这些记录的条数和 score 均值")
    slice_snap = QuerySnapshot(
        "query-results/slice10.json",
        result_rows=10,
        query_limit=10,
        rows_scanned=22960,
        dataset_id="ds_slice",
        resource="submit_record",
    )
    broad_snap = QuerySnapshot(
        "query-results/full.json",
        result_rows=22960,
        rows_scanned=22960,
        dataset_id="ds_full",
        resource="submit_record",
    )
    ctx.register_query_snapshot(slice_snap)
    ctx.register_query_snapshot(broad_snap)

    binding = resolve_aggregate_binding(
        {"result_ref": "query-results/full.json"},
        metrics=[{"op": "count", "as": "n"}, {"op": "mean", "field": "score", "as": "avg"}],
        dimensions=None,
        bind=BindMode.AUTO,
        analysis_context=ctx,
        batch_snapshots=[slice_snap, broad_snap],
    )
    assert binding.error is None
    assert binding.result_ref == "query-results/slice10.json"
    assert binding.corrected is True
    assert "rule_chain_slice" in (binding.trace or {}).get("resolver", "")


def test_class_wide_priority_over_not_these_n_rows():
    ctx = _ctx("统计全班不同学生（全班口径，不是这10条）")
    slice_snap = QuerySnapshot(
        "query-results/slice10.json",
        result_rows=10,
        query_limit=10,
        rows_scanned=22960,
        dataset_id="ds_slice",
        resource="submit_record",
    )
    broad_snap = QuerySnapshot(
        "query-results/full.json",
        result_rows=22960,
        rows_scanned=22960,
        dataset_id="ds_full",
        resource="submit_record",
    )
    ctx.register_query_snapshot(slice_snap)
    ctx.register_query_snapshot(broad_snap)

    binding = resolve_aggregate_binding(
        {"result_ref": "query-results/slice10.json"},
        metrics=[{"op": "count_distinct", "field": "student_ID", "as": "n"}],
        dimensions=None,
        bind=BindMode.FRESH,
        analysis_context=ctx,
        batch_snapshots=[slice_snap, broad_snap],
    )
    assert binding.error is None
    assert binding.result_ref == "query-results/full.json"
    assert "rule_fresh_broad" in (binding.trace or {}).get("resolver", "")


def test_explicit_dataset_id_rejects_broad_when_teacher_wants_slice():
    sid = "explicit-slice-reject"
    append_dataset(
        sid,
        DatasetRecord(
            dataset_id="ds_broad",
            result_ref="query-results/full.json",
            user_turn=1,
            result_rows=22960,
            rows_scanned=22960,
        ),
    )
    ctx = _ctx("汇总这些记录的均值", session_id=sid, user_turn=1)
    binding = resolve_aggregate_binding(
        {"dataset_id": "ds_broad"},
        metrics=[{"op": "mean", "field": "score", "as": "avg"}],
        dimensions=None,
        bind=BindMode.AUTO,
        analysis_context=ctx,
        batch_snapshots=[],
    )
    assert binding.error
    assert "全量" in binding.error or "切片" in binding.error


def test_validate_rejects_cross_turn_class_wide_without_teacher_cue():
    bctx = build_binding_context(
        inp={},
        metrics=[{"op": "mean", "field": "score", "as": "avg"}],
        dimensions=None,
        bind="auto",
        analysis_context=_ctx("直接 aggregate 均值", user_turn=2),
        batch_snapshots=[],
    )
    decision = DatasetBindingDecision(
        scope="class_wide",
        dataset_id="ds_broad",
        result_ref="query-results/full.json",
        resolver="llm",
    )
    append_dataset(
        "rule-test",
        DatasetRecord(
            dataset_id="ds_broad",
            result_ref="query-results/full.json",
            user_turn=1,
            result_rows=22960,
            rows_scanned=22960,
        ),
    )
    err = validate_decision(decision, bctx)
    assert err
    assert "class_wide" in err
    assert "user_turn=1" in err

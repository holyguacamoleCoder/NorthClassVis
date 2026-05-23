"""Semantic aggregate binding (Q1 slice vs Q2 class-wide)."""

import os
import sys
from pathlib import Path

AGENT_ROOT = Path(__file__).resolve().parents[1]
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))

import runtime_bootstrap  # noqa: F401, E402

os.environ["BINDING_RESOLVER_DISABLE_LLM"] = "1"

from loop_state import AnalysisToolContext, QuerySnapshot  # noqa: E402
from tools.runtime.binding.types import BindMode  # noqa: E402
from tools.runtime.binding.pipeline import resolve_aggregate_binding  # noqa: E402


def _ctx(msg: str) -> AnalysisToolContext:
    c = AnalysisToolContext(session_id="sem-test", user_turn=1)
    c.current_user_message = msg
    return c


def test_q1_chain_corrects_full_ref_to_slice():
    """Parallel limit=10 + full: teacher asks to summarize 这些 records → slice."""
    ctx = _ctx("先找出 Class1 得分最低的前 10 条提交，再汇总这些记录的分数分布（条数、均值）。")
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
    batch = [slice_snap, broad_snap]

    binding = resolve_aggregate_binding(
        {
            "result_ref": "query-results/full.json",
        },
        metrics=[
            {"op": "count", "field": "score", "as": "n"},
            {"op": "mean", "field": "score", "as": "avg"},
        ],
        dimensions=None,
        bind=BindMode.AUTO,
        analysis_context=ctx,
        batch_snapshots=batch,
        llm_client=None,
    )
    assert binding.error is None
    assert binding.result_ref == "query-results/slice10.json"
    assert binding.dataset_id == "ds_slice"
    assert binding.corrected is True
    assert binding.trace and binding.trace.get("gate_triggered") is True


def test_q2_class_wide_keeps_broad_ref():
    ctx = _ctx("用 Class1 的数据，说一下这个班提交的整体情况：规模、分数水平、偏科知识点。")
    broad = QuerySnapshot(
        "query-results/full.json",
        result_rows=22960,
        rows_scanned=22960,
        dataset_id="ds_full",
        resource="submit_record",
    )
    ctx.register_query_snapshot(broad)
    binding = resolve_aggregate_binding(
        {"result_ref": "query-results/full.json"},
        metrics=[
            {"op": "count_distinct", "field": "student_ID", "as": "students"},
            {"op": "mean", "field": "score", "as": "avg"},
        ],
        dimensions=None,
        bind=BindMode.AUTO,
        analysis_context=ctx,
        batch_snapshots=[broad],
        llm_client=None,
    )
    assert binding.error is None
    assert binding.result_ref == "query-results/full.json"
    assert binding.dataset_id == "ds_full"

"""Tests for query ↔ aggregate oscillation guards."""

from __future__ import annotations

import runtime_bootstrap  # noqa: F401, E402

from hints.data_chain_guard import (
    aggregate_errors_in_batch,
    normalize_aggregate_error,
    normalize_query_data_signature,
    query_signatures_in_batch,
    should_break_aggregate_retry_loop,
    should_break_repeated_query_loop,
)
from loop import AgentLoop
from loop_limits import AGGREGATE_RETRY_LOOP_WINDOW
from loop_state import LoopState


def test_normalize_aggregate_error_strips_dataset_id():
    raw = (
        "Error: 绑定 scope=class_wide 但 ds_5b221d377b39 仅为 255 行。"
        "全班统计请先 query_data（省略 limit）再 aggregate。"
    )
    sig = normalize_aggregate_error(raw)
    assert sig is not None
    assert "ds_5b221d377b39" not in sig
    assert "ds_*" in sig


def test_normalize_query_ignores_select_and_order_by():
    a = {
        "name": "query_data",
        "arguments": {
            "resource": "week_aggregation",
            "classes": ["Class1"],
            "week_range": [13, 15],
            "select": ["student_ID", "peak_value"],
        },
    }
    b = {
        "name": "query_data",
        "arguments": {
            "resource": "week_aggregation",
            "classes": ["Class1"],
            "week_range": [13, 15],
            "select": ["student_ID", "peak_value"],
            "order_by": [{"field": "peak_value", "dir": "desc"}],
        },
    }
    assert normalize_query_data_signature(a) == normalize_query_data_signature(b)


def test_aggregate_retry_loop_triggers_after_three_same_errors():
    sig = normalize_aggregate_error(
        "Error: 绑定 scope=class_wide 但 ds_aaa 仅为 255 行。"
    )
    recent = [sig, sig, sig]
    assert should_break_aggregate_retry_loop(recent, window=AGGREGATE_RETRY_LOOP_WINDOW)


def test_repeated_query_after_aggregate_failures():
    sig = '{"resource": "week_aggregation", "classes": ["Class1"], "week_range": [13, 15], "majors": null}'
    recent = [sig, sig, sig]
    assert should_break_repeated_query_loop(
        recent,
        window=5,
        repeat_threshold=3,
    )


def test_agent_loop_data_chain_guard_on_session_pattern():
    loop = AgentLoop(LoopState(messages=[]))
    agg_err = (
        "Error: 绑定 scope=class_wide 但 ds_5b221d377b39 仅为 255 行。"
        "全班统计请先 query_data（省略 limit）再 aggregate。"
    )
    q_call = {
        "id": "q1",
        "name": "query_data",
        "arguments": {
            "resource": "week_aggregation",
            "classes": ["Class1"],
            "week_range": [13, 15],
        },
    }
    a_call = {
        "id": "a1",
        "name": "aggregate_data",
        "arguments": {"input": {"result_ref": "query-results/x.json"}},
    }

    triggered = False
    for i in range(AGGREGATE_RETRY_LOOP_WINDOW):
        if loop._should_break_data_chain_oscillation(
            [a_call],
            [{"tool_call_id": "a1", "content": agg_err}],
        ):
            triggered = True
            break
        loop._should_break_data_chain_oscillation(
            [q_call],
            [{"tool_call_id": "q1", "content": "ok"}],
        )
    assert triggered


def test_aggregate_errors_in_batch_returns_one_sig():
    calls = [{"id": "a1", "name": "aggregate_data"}]
    results = [{"tool_call_id": "a1", "content": "Error: 绑定 scope=class_wide 但 ds_x 仅为 1 行。"}]
    assert len(aggregate_errors_in_batch(calls, results)) == 1


def test_query_signatures_in_batch():
    calls = [
        {
            "id": "q1",
            "name": "query_data",
            "arguments": {"resource": "week_aggregation", "classes": ["Class1"]},
        }
    ]
    sigs = query_signatures_in_batch(calls)
    assert len(sigs) == 1

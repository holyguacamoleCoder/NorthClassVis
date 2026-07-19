"""Tests for query ↔ aggregate oscillation guards."""

from __future__ import annotations

import runtime_bootstrap  # noqa: F401, E402

from hints.data_chain_guard import (
    aggregate_errors_in_batch,
    build_oscillation_event,
    is_exploration_only_batch,
    normalize_aggregate_error,
    normalize_query_data_signature,
    query_signatures_in_batch,
    should_break_aggregate_retry_loop,
    should_break_repeated_query_loop,
)
from loop import AgentLoop
from loop_limits import AGGREGATE_RETRY_LOOP_WINDOW, EXPLORATION_THRASH_WINDOW
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


def test_agent_loop_data_chain_guard_soft_then_hard():
    """First hit soft-redirects; second hit after soft_hits hard-fuses."""
    loop = AgentLoop(LoopState(messages=[]))
    agg_err = (
        "Error: 绑定 scope=class_wide 但 ds_5b221d377b39 仅为 255 行。"
        "全班统计请先 query_data（省略 limit）再 aggregate。"
    )
    a_call = {
        "id": "a1",
        "name": "aggregate_data",
        "arguments": {"input": {"result_ref": "query-results/x.json"}},
    }
    results = [{"tool_call_id": "a1", "content": agg_err}]

    soft_ev = None
    for _ in range(AGGREGATE_RETRY_LOOP_WINDOW):
        soft_ev = loop._detect_data_chain_oscillation([a_call], results)
        if soft_ev is not None:
            break
    assert soft_ev is not None
    assert soft_ev.soft is True
    assert soft_ev.kind == "aggregate_error_retry"
    assert "探索" in "\n".join(soft_ev.next_method_lines)

    # Mimic loop soft path: count soft hit + clear fingerprints so exploration can continue
    loop._oscillation_soft_hits[soft_ev.kind] = 1
    loop._clear_oscillation_fingerprints(soft_ev.kind)
    loop._recent_exploration_flags.clear()

    hard_ev = None
    for _ in range(AGGREGATE_RETRY_LOOP_WINDOW):
        hard_ev = loop._detect_data_chain_oscillation([a_call], results)
        if hard_ev is not None:
            break
    assert hard_ev is not None
    assert hard_ev.soft is False
    assert loop._should_break_data_chain_oscillation([a_call], results) is True


def test_exploration_only_batch_detects_meta_and_peek():
    assert is_exploration_only_batch(
        [{"name": "inspect_schema", "arguments": {"resource": "submit_record"}}]
    )
    assert is_exploration_only_batch(
        [
            {"name": "list_datasets", "arguments": {"tail": 10}},
            {"name": "todo_write", "arguments": {"items": []}},
        ]
    )
    assert is_exploration_only_batch(
        [
            {
                "name": "query_data",
                "arguments": {
                    "resource": "submit_record",
                    "class": "Class2",
                    "limit": 10,
                },
            }
        ]
    )
    # Full query is not "exploration-only" (handled by repeated_query kind)
    assert not is_exploration_only_batch(
        [
            {
                "name": "query_data",
                "arguments": {"resource": "submit_record", "class": "Class2"},
            }
        ]
    )
    assert not is_exploration_only_batch(
        [
            {
                "name": "aggregate_data",
                "arguments": {"input": {"dataset_id": "ds_abc"}, "dimensions": ["student_ID"]},
            }
        ]
    )


def test_cold_start_exploration_soft_then_hard():
    """Pure inspect/list loops (no prior data-chain soft) still get soft→hard."""
    loop = AgentLoop(LoopState(messages=[]))
    explore = {"name": "inspect_schema", "arguments": {"resource": "submit_record"}}

    soft_ev = None
    for _ in range(EXPLORATION_THRASH_WINDOW):
        soft_ev = loop._detect_data_chain_oscillation([explore], [])
        if soft_ev is not None:
            break
    assert soft_ev is not None
    assert soft_ev.kind == "exploration_thrash"
    assert soft_ev.soft is True

    loop._oscillation_soft_hits[soft_ev.kind] = 1
    loop._clear_oscillation_fingerprints(soft_ev.kind)

    hard_ev = None
    for _ in range(EXPLORATION_THRASH_WINDOW):
        hard_ev = loop._detect_data_chain_oscillation([explore], [])
        if hard_ev is not None:
            break
    assert hard_ev is not None
    assert hard_ev.soft is False


def test_after_method_soft_exploration_hard_fuses_immediately():
    """软提示探索 → 再震荡 → 熔断（不再给第二次探索 soft）。"""
    loop = AgentLoop(LoopState(messages=[]))
    loop._oscillation_soft_hits["repeated_identical_query"] = 1
    loop._recent_exploration_flags.clear()

    explore = {"name": "list_datasets", "arguments": {"tail": 10}}
    peek = {
        "name": "query_data",
        "arguments": {"resource": "submit_record", "class": "Class2", "limit": 1},
    }
    hard_ev = None
    for i in range(EXPLORATION_THRASH_WINDOW):
        batch = [explore] if i % 2 == 0 else [peek]
        hard_ev = loop._detect_data_chain_oscillation(batch, [])
        if hard_ev is not None:
            break
    assert hard_ev is not None
    assert hard_ev.kind == "exploration_thrash"
    assert hard_ev.soft is False
    assert "aggregate_data" in "\n".join(hard_ev.next_method_lines)


def test_exploration_thrash_cleared_by_aggregate():
    loop = AgentLoop(LoopState(messages=[]))
    for _ in range(EXPLORATION_THRASH_WINDOW - 1):
        loop._detect_data_chain_oscillation(
            [{"name": "inspect_schema", "arguments": {"resource": "submit_record"}}],
            [],
        )
    loop._detect_data_chain_oscillation(
        [
            {
                "id": "a1",
                "name": "aggregate_data",
                "arguments": {
                    "input": {"dataset_id": "ds_x"},
                    "dimensions": ["student_ID"],
                    "metrics": [{"op": "sum", "field": "score", "as": "total"}],
                    "order_by": [{"field": "total", "dir": "asc"}],
                    "limit": 5,
                },
            }
        ],
        [{"tool_call_id": "a1", "content": "[Summary] ok"}],
    )
    assert loop._recent_exploration_flags == []
    ev = loop._detect_data_chain_oscillation(
        [{"name": "list_datasets", "arguments": {}}],
        [],
    )
    assert ev is None or ev.kind != "exploration_thrash"


def test_repeated_query_soft_invites_exploration():
    text = "\n".join(
        build_oscillation_event("repeated_identical_query", soft=True).next_method_lines
    )
    assert "探索" in text
    assert "aggregate_data" in text
    assert "enrich_data" in text


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

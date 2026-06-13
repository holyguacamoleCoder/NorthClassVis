"""Tests for online binding accuracy eval."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
AGENT_ROOT = REPO_ROOT / "backend" / "agent"
SCRIPT = REPO_ROOT / "backend" / "agent" / "eval" / "run_binding_online_eval.py"
SCENARIOS = REPO_ROOT / "backend" / "agent" / "eval" / "fixtures" / "binding_online_scenarios.json"
JSON_OUT = REPO_ROOT / "data" / "eval" / "binding_accuracy_online.json"

if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))

import runtime_bootstrap  # noqa: F401, E402

from data.dataset_registry import DatasetRecord  # noqa: E402
from eval.binding_judge import judge_aggregate, recover_meta_from_partial_json  # noqa: E402
from eval.run_binding_online_eval import (  # noqa: E402
    extract_aggregate_events,
    load_scenarios,
    evaluate_scenario_run,
)

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("numpy") is None,
    reason="numpy 未安装",
)


def test_scenarios_fixture_has_at_least_eight():
    scenarios = load_scenarios(SCENARIOS)
    assert len(scenarios) >= 8
    ids = {s.id for s in scenarios}
    assert "chain_slice_two_turns" in ids
    assert "class_wide_after_slice_new_turn" in ids


def test_judge_slice_and_broad():
    catalog = [
        DatasetRecord(
            dataset_id="ds_s",
            result_ref="query-results/s.json",
            user_turn=1,
            result_rows=10,
            query_limit=10,
            rows_scanned=20000,
        ),
        DatasetRecord(
            dataset_id="ds_b",
            result_ref="query-results/b.json",
            user_turn=1,
            result_rows=9000,
            query_limit=None,
            rows_scanned=9000,
        ),
    ]
    ok, _ = judge_aggregate(
        "slice",
        meta={"dataset_id": "ds_s", "result_ref": "query-results/s.json"},
        catalog=catalog,
        content='{"rows":[]}',
    )
    assert ok
    ok, _ = judge_aggregate(
        "broad",
        meta={"dataset_id": "ds_b", "result_ref": "query-results/b.json"},
        catalog=catalog,
        content='{"rows":[]}',
    )
    assert ok


def test_judge_allow_cross_turn_explicit_from_tool_input():
    catalog = [
        DatasetRecord(
            dataset_id="ds_slice",
            result_ref="query-results/slice.json",
            user_turn=1,
            result_rows=10,
            query_limit=10,
            rows_scanned=22960,
        ),
    ]
    partial = (
        '{"rows":[[0.0]],"meta":{"rows_scanned":10,"binding_decision":"prior_turn_dataset",'
        '"result_ref":"query-results/out.json"'
    )
    ok, reason = judge_aggregate(
        "allow_cross_turn_explicit",
        meta={"rows_scanned": 10, "binding_decision": "prior_turn_dataset"},
        catalog=catalog,
        content=partial,
        tool_input={"input": {"dataset_id": "ds_slice"}, "metrics": []},
        current_user_turn=2,
    )
    assert ok, reason


def test_judge_reject_cross_turn():
    ok, reason = judge_aggregate(
        "reject_cross_turn",
        meta={},
        catalog=[],
        content="Error: result_ref 来自上一轮提问，不能自动续用。",
    )
    assert ok
    assert "cross_turn" in reason or "aggregate_error" in reason


def test_recover_meta_from_truncated_json():
    partial = (
        '{"schema":[],"rows":[[2.8]],"meta":{"rows_scanned":10,'
        '"binding_decision":"chain_slice:rule","ref_corrected":true,'
        '"binding_trace":{"bound_result_ref":"query-results/slice.json"'
    )
    meta = recover_meta_from_partial_json(partial)
    assert meta["rows_scanned"] == 10
    assert meta["binding_decision"] == "chain_slice:rule"
    assert meta["ref_corrected"] is True
    ok, reason = judge_aggregate(
        "slice",
        meta=meta,
        catalog=[],
        content=partial,
    )
    assert ok, reason


def test_judge_slice_after_ref_corrected():
    """Model passed broad ref; binding corrected to slice — judge by bound rows, not tool_input."""
    catalog = [
        DatasetRecord(
            dataset_id="ds_slice",
            result_ref="query-results/slice.json",
            user_turn=1,
            result_rows=10,
            query_limit=10,
            rows_scanned=22960,
        ),
        DatasetRecord(
            dataset_id="ds_broad",
            result_ref="query-results/broad.json",
            user_turn=1,
            result_rows=22960,
            query_limit=None,
            rows_scanned=22960,
        ),
    ]
    ok, reason = judge_aggregate(
        "slice",
        meta={
            "ref_corrected": True,
            "rows_scanned": 10,
            "binding_decision": "chain_slice:rule",
            "binding_trace": {
                "resolver": "rule_chain_slice",
                "bound_result_ref": "query-results/slice.json",
                "bound_dataset_id": "ds_slice",
            },
        },
        catalog=catalog,
        content='{"rows":[]}',
        tool_input={
            "input": {"result_ref": "query-results/broad.json"},
            "metrics": [{"op": "mean", "field": "score", "as": "avg"}],
        },
    )
    assert ok, reason


def test_extract_aggregate_events_turn_ordinals():
    messages = [
        {"role": "user", "content": "q1"},
        {
            "role": "assistant",
            "tool_calls": [
                {
                    "id": "c1",
                    "function": {
                        "name": "aggregate_data",
                        "arguments": '{"metrics":[{"op":"count","as":"n"}]}',
                    },
                }
            ],
        },
        {"role": "tool", "tool_call_id": "c1", "content": '{"meta":{"dataset_id":"a"}}'},
        {"role": "user", "content": "q2"},
        {
            "role": "assistant",
            "tool_calls": [
                {
                    "id": "c2",
                    "function": {
                        "name": "aggregate_data",
                        "arguments": "{}",
                    },
                }
            ],
        },
        {"role": "tool", "tool_call_id": "c2", "content": "Error: 上一轮"},
    ]
    events = extract_aggregate_events(messages)
    assert len(events) == 2
    assert events[0]["turn_index"] == 0 and events[0]["ordinal"] == 1
    assert events[1]["turn_index"] == 1 and events[1]["ordinal"] == 1
    assert events[1]["is_error"] is True


def test_dry_run_script_smoke(tmp_path):
    json_out = tmp_path / "out.json"
    report_out = tmp_path / "report.md"
    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--dry-run",
            "--runs",
            "1",
            "--scenario",
            "chain_slice_two_turns",
            "--json-out",
            str(json_out),
            "--report-out",
            str(report_out),
        ],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    data = json.loads(json_out.read_text(encoding="utf-8"))
    assert data["N_aggregates"] >= 1
    assert data["accuracy_pct"] == 100.0
    assert report_out.is_file()


@pytest.mark.integration
def test_single_scenario_live_one_run():
    if not os.environ.get("RUN_BINDING_ONLINE"):
        pytest.skip("set RUN_BINDING_ONLINE=1 to run live LLM integration")
    if not (os.environ.get("OPENAI_API_KEY") or "").strip():
        pytest.skip("OPENAI_API_KEY not set")

    scenarios = load_scenarios(SCENARIOS)
    scenario = next(s for s in scenarios if s.id == "chain_slice_two_turns")
    from common.llm_client import LLMClient

    result = evaluate_scenario_run(scenario, run_index=0, llm_client=LLMClient())
    assert result["status"] in ("ok", "timeout", "error", "skipped")
    if result["status"] == "ok":
        assert result.get("aggregate_judgments")

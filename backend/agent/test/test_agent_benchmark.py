"""Tests for the universal agent benchmark harness."""

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
SCRIPT = AGENT_ROOT / "eval" / "run_agent_benchmark.py"
SCENARIOS_DIR = AGENT_ROOT / "eval" / "fixtures" / "scenarios"

if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))

import runtime_bootstrap  # noqa: F401, E402

from data.dataset_registry import DatasetRecord  # noqa: E402
from eval.binding_judge import judge_aggregate  # noqa: E402
from eval.runner import build_dry_run_messages, run_scenario  # noqa: E402
from eval.schema import load_scenarios, validate_scenarios  # noqa: E402
from eval.trace import extract_tool_events  # noqa: E402

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("numpy") is None,
    reason="numpy 未安装",
)


def test_scenarios_load_and_validate():
    scenarios = load_scenarios(SCENARIOS_DIR)
    assert len(scenarios) >= 30
    errors = validate_scenarios(scenarios)
    assert not errors, errors
    ids = {s.id for s in scenarios}
    assert "chain_slice_two_turns" in ids
    assert "tools_query_limit_10" in ids
    assert "scope_class_chip" in ids
    assert "efficiency_short_query" in ids


def test_tags_filter():
    binding = load_scenarios(SCENARIOS_DIR, tags=["binding"])
    assert binding
    assert all("binding" in s.tags for s in binding)


def test_turns_are_teacher_length():
    scenarios = load_scenarios(SCENARIOS_DIR)
    assert all(len(s.turns) == 3 for s in scenarios), [
        (s.id, len(s.turns)) for s in scenarios if len(s.turns) != 3
    ]
    # turns 应为教师自然语言，不应含典型开发指令
    dev_markers = ("query_data", "aggregate_data", "list_datasets", "limit=", "dataset_id", "inspect_schema")
    for s in scenarios:
        blob = "\n".join(s.turns)
        hits = [m for m in dev_markers if m in blob]
        assert not hits, f"{s.id} turns contain dev markers: {hits}"


def test_extract_tool_events_turn_ordinals():
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
                    "function": {"name": "aggregate_data", "arguments": "{}"},
                }
            ],
        },
        {"role": "tool", "tool_call_id": "c2", "content": "Error: 上一轮"},
    ]
    events = extract_tool_events(messages)
    assert len(events) == 2
    assert events[0].turn_index == 0 and events[0].ordinal == 1
    assert events[1].turn_index == 1 and events[1].is_error is True


def test_judge_still_works():
    catalog = [
        DatasetRecord(
            dataset_id="ds_s",
            result_ref="query-results/s.json",
            user_turn=1,
            result_rows=10,
            query_limit=10,
            rows_scanned=20000,
        )
    ]
    ok, _ = judge_aggregate(
        "slice",
        meta={"dataset_id": "ds_s", "result_ref": "query-results/s.json"},
        catalog=catalog,
        content='{"rows":[]}',
    )
    assert ok


def test_dry_run_single_scenario():
    scenarios = load_scenarios(SCENARIOS_DIR, scenario_id="chain_slice_two_turns")
    assert len(scenarios) == 1
    tr = run_scenario(scenarios[0], run_index=0, dry_run=True)
    assert tr.status in ("ok", "failed")
    bind = [m for m in tr.metric_results if m["name"] == "binding_accuracy"]
    assert bind
    assert all(m["passed"] for m in bind)
    # efficiency columns present
    names = {m["name"] for m in tr.metric_results}
    assert "latency" in names
    assert "tokens_cost" in names


def test_dry_run_scope_injects_hint():
    scenarios = load_scenarios(SCENARIOS_DIR, scenario_id="scope_class_chip")
    msgs = build_dry_run_messages(scenarios[0])
    user = next(m for m in msgs if m["role"] == "user")
    assert "[系统·本轮范围]" in user["content"]
    assert "Class1" in user["content"]


def test_dry_run_script_smoke(tmp_path):
    json_out = tmp_path / "out.json"
    report_out = tmp_path / "report.md"
    checkpoint_out = tmp_path / "partial.jsonl"
    manifest_out = tmp_path / "manifest.json"
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
            "--checkpoint-out",
            str(checkpoint_out),
            "--manifest-out",
            str(manifest_out),
        ],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    data = json.loads(json_out.read_text(encoding="utf-8"))
    assert data["N_scenarios"] == 1
    assert data.get("manifest", {}).get("benchmark_run_id")
    assert "pass_at_1_pct" in data
    assert report_out.is_file()
    assert checkpoint_out.is_file()
    assert manifest_out.is_file()
    lines = checkpoint_out.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) >= 2
    assert json.loads(lines[0])["type"] == "manifest"
    assert json.loads(lines[-1])["type"] == "run"


def test_manifest_fingerprint_stable():
    from eval.manifest import build_run_manifest, scenario_fingerprint, collect_scenario_paths

    paths = collect_scenario_paths(SCENARIOS_DIR)
    fp1 = scenario_fingerprint(paths)
    fp2 = scenario_fingerprint(paths)
    assert fp1 == fp2
    m = build_run_manifest(
        benchmark_run_id="test-run",
        scenarios_root=SCENARIOS_DIR,
        scenario_ids=["a"],
        runs_per_scenario=1,
        dry_run=True,
        pass_strategy="majority",
        timeout_sec=180,
        keep_session="on-failure",
        checkpoint_path=Path("data/eval/x.jsonl"),
        json_out=Path("data/eval/x.json"),
        report_out=Path("docs/eval/x.md"),
    )
    assert m["benchmark_run_id"] == "test-run"
    assert m["scenario_fingerprint"] == fp1


def test_rebuild_ui_messages_from_scenario_turns():
    from eval.repair_ui import parse_bench_session_id, rebuild_ui_messages_from_turns
    from session.ui_scope import compose_llm_user_content

    assert parse_bench_session_id("agent-bench-chain_slice_two_turns-r2") == (
        "chain_slice_two_turns",
        2,
    )
    hint = "[系统·本轮范围] Class1"
    # Simulate drop bug: only last user remains; earlier turns are final-assistant segments.
    messages = [
        {
            "role": "assistant",
            "tool_calls": [{"id": "c1", "function": {"name": "query_data", "arguments": "{}"}}],
        },
        {"role": "tool", "tool_call_id": "c1", "content": "{}"},
        {"role": "assistant", "content": "答1"},
        {
            "role": "assistant",
            "tool_calls": [{"id": "c2", "function": {"name": "aggregate_data", "arguments": "{}"}}],
        },
        {"role": "tool", "tool_call_id": "c2", "content": "{}"},
        {"role": "assistant", "content": "答2"},
        {"role": "user", "content": compose_llm_user_content("第三问", hint)},
        {"role": "assistant", "content": "答3"},
    ]
    turns = ["第一问", "第二问", "第三问"]
    ui = rebuild_ui_messages_from_turns(messages, turns)
    users = [m for m in ui if m["role"] == "user"]
    assert [u["content"] for u in users] == turns
    assert "系统" not in "".join(u["content"] for u in users)
    # Each Q followed by its answer
    assert ui[0]["content"] == "第一问"
    assert ui[3]["content"] == "答1"
    assert ui[4]["content"] == "第二问"
    assert ui[7]["content"] == "答2"
    assert ui[8]["content"] == "第三问"
    assert ui[9]["content"] == "答3"


@pytest.mark.integration
def test_single_scenario_live_one_run():
    if not (os.environ.get("RUN_AGENT_ONLINE") or os.environ.get("RUN_BINDING_ONLINE")):
        pytest.skip("set RUN_AGENT_ONLINE=1 to run live LLM integration")
    if not (os.environ.get("OPENAI_API_KEY") or "").strip():
        pytest.skip("OPENAI_API_KEY not set")

    scenarios = load_scenarios(SCENARIOS_DIR, scenario_id="chain_slice_two_turns")
    from common.llm_client import LLMClient

    result = run_scenario(scenarios[0], run_index=0, llm_client=LLMClient())
    assert result.status in ("ok", "failed", "timeout", "error", "skipped", "incomplete")
    if result.status == "ok":
        assert result.tool_calls

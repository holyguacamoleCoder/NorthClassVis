"""Tests for tool run lifecycle registry and modify resolver."""

from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

import pytest

_BACKEND_ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

from agent.common.paths import AGENT_STATE_DIR  # noqa: E402
from agent.runs.derive import plan_derive  # noqa: E402
from agent.runs.models import RunStatus, ToolRun  # noqa: E402
from agent.runs.modify_resolver import (  # noqa: E402
    extract_patch_from_message,
    looks_like_modify,
    resolve_modify_intent,
)
from agent.runs.registry import RunRegistry  # noqa: E402


@pytest.fixture()
def isolated_agent_state(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "agent.runs.registry.AGENT_STATE_DIR",
        tmp_path / ".agent",
    )
    monkeypatch.setattr(
        "agent.common.paths.AGENT_STATE_DIR",
        tmp_path / ".agent",
    )
    return tmp_path / ".agent"


def test_plan_derive_requery_on_group_by_change(isolated_agent_state):
    parent = ToolRun(
        run_id="p1",
        session_id="sess1",
        tool_name="query_data",
        status=RunStatus.COMPLETED,
        params={"resource": "submit_record", "class": "Class1", "group_by": ["month"]},
        result_ref="query-results/a.json",
    )
    plan = plan_derive(parent, {"group_by": ["week"]})
    assert plan.strategy == "requery"
    assert plan.merged_params["group_by"] == ["week"]
    assert plan.merged_params["class"] == "Class1"


def test_plan_derive_reaggregate_on_metrics_only(isolated_agent_state):
    parent = ToolRun(
        run_id="p1",
        session_id="sess1",
        tool_name="query_data",
        status=RunStatus.COMPLETED,
        params={"resource": "submit_record", "class": "Class1"},
        result_ref="query-results/a.json",
    )
    plan = plan_derive(parent, {"metrics": [{"op": "mean", "field": "score"}]})
    assert plan.strategy == "reaggregate"
    assert plan.reuse_result_ref == "query-results/a.json"


def test_plan_derive_reaggregate_on_dimensions_from_ungrouped_query(isolated_agent_state):
    parent = ToolRun(
        run_id="p1",
        session_id="sess1",
        tool_name="query_data",
        status=RunStatus.COMPLETED,
        params={"resource": "submit_record", "class": "Class1"},
        result_ref="query-results/a.json",
        dataset_id="ds1",
    )
    plan = plan_derive(parent, {"group_by": ["class"]})
    assert plan.strategy == "reaggregate"
    assert plan.patch.get("dimensions") == ["class"]
    assert "group_by" not in plan.patch
    assert plan.reuse_result_ref == "query-results/a.json"
    assert plan.reuse_dataset_id == "ds1"


def test_extract_patch_dimensions_when_parent_ungrouped():
    patch = extract_patch_from_message(
        "按班级统计及格率",
        {"resource": "submit_record"},
        parent_tool="query_data",
    )
    assert patch.get("dimensions") == ["class"]
    assert "group_by" not in patch
    assert patch.get("metrics")


def test_plan_derive_reaggregate_on_aggregate_parent(isolated_agent_state):
    parent = ToolRun(
        run_id="agg1",
        session_id="sess1",
        tool_name="aggregate_data",
        status=RunStatus.COMPLETED,
        params={
            "metrics": [{"op": "count", "as": "n"}],
            "input": {"result_ref": "query-results/q.json", "dataset_id": "ds1"},
        },
        result_ref="query-results/agg.json",
    )
    plan = plan_derive(parent, {"dimensions": ["class"]})
    assert plan.strategy in ("reaggregate", "reuse_aggregate")
    assert plan.reuse_result_ref == "query-results/q.json"
    assert plan.reuse_dataset_id == "ds1"


def test_registry_begin_complete_and_list(isolated_agent_state):
    reg = RunRegistry()
    run_id = reg.begin_run(
        session_id="sess-a",
        tool_name="query_data",
        params={"resource": "submit_record", "class": "Class1"},
        job_id="job1",
        user_turn=1,
    )
    reg.complete_run(run_id, result_ref="query-results/x.json", dataset_id="ds1")
    runs = reg.list_runs("sess-a")
    assert len(runs) == 1
    assert runs[0].status == RunStatus.COMPLETED
    assert runs[0].result_ref == "query-results/x.json"


def test_build_modify_bootstrap_call_reaggregate(isolated_agent_state):
    import json

    from agent.runs.modify_bootstrap import build_modify_bootstrap_call

    reg = RunRegistry()
    parent_id = reg.begin_run(
        session_id="sess-boot",
        tool_name="query_data",
        params={"resource": "submit_record", "class": "Class1"},
        job_id="job1",
    )
    reg.complete_run(
        parent_id,
        result_ref="query-results/q.json",
        dataset_id="ds1",
    )
    ctx = {
        "parent_run_id": parent_id,
        "strategy": "reaggregate",
        "patch": {"dimensions": ["class"]},
        "parent_params": {"resource": "submit_record", "class": "Class1"},
    }
    built = build_modify_bootstrap_call(ctx, run_registry=reg)
    assert built is not None
    tool_calls, _hint = built
    assert tool_calls[0]["name"] == "aggregate_data"
    assert ctx.get("_bootstrapped") is True
    args = json.loads(tool_calls[0]["arguments"])
    assert args.get("dimensions") == ["class"]
    assert args.get("input", {}).get("dataset_id") == "ds1"


def test_registry_supersede_on_derive(isolated_agent_state):
    reg = RunRegistry()
    parent_id = reg.begin_run(
        session_id="sess-b",
        tool_name="query_data",
        params={"resource": "submit_record", "group_by": ["month"]},
        job_id="job1",
    )
    reg.complete_run(parent_id, result_ref="query-results/p.json")
    child_id = reg.begin_run(
        session_id="sess-b",
        tool_name="query_data",
        params={"resource": "submit_record", "group_by": ["week"]},
        job_id="job2",
        parent_run_id=parent_id,
        patch={"group_by": ["week"]},
    )
    reg.mark_superseded(parent_id, child_id)
    parent = reg.get_run(parent_id)
    child = reg.get_run(child_id)
    assert parent.status == RunStatus.SUPERSEDED
    assert parent.superseded_by == child_id
    assert child.parent_run_id == parent_id


def test_modify_resolver_detects_group_by_change(isolated_agent_state):
    reg = RunRegistry()
    run_id = reg.begin_run(
        session_id="sess-c",
        tool_name="query_data",
        params={"resource": "submit_record", "group_by": ["month"]},
        job_id="job1",
    )
    reg.complete_run(run_id, result_ref="query-results/r.json")
    runs = reg.list_runs("sess-c")
    hint = resolve_modify_intent("不对，改成按周汇总", runs)
    assert hint is not None
    assert hint.parent_run_id == run_id
    assert hint.patch.get("group_by") == ["week"]


def test_extract_patch_from_message():
    patch = extract_patch_from_message("改成按季度分组")
    assert patch.get("group_by") == ["quarter"]
    assert looks_like_modify("改成按季度")


def test_strip_run_modify_from_user_content():
    from agent.runs.apply import strip_run_modify_from_user_content

    raw = (
        "[run_modify]\n{\"parent_run_id\": \"abc\"}\n[/run_modify]\n"
        "这是对上一轮数据计算的修改：请继承 parent 未改条件，仅应用 patch；"
        "优先使用 derive_from_run_id / 合并参数，避免不必要的全量重查。\n\n"
        "改成按周汇总"
    )
    assert strip_run_modify_from_user_content(raw) == "改成按周汇总"


def test_cancel_run_marks_cancelled(isolated_agent_state):
    reg = RunRegistry()
    run_id = reg.begin_run(
        session_id="sess-d",
        tool_name="query_data",
        params={"resource": "submit_record"},
        job_id="job9",
    )
    assert reg.cancel_run(run_id) is True
    run = reg.get_run(run_id)
    assert run.status in (RunStatus.CANCELLED, RunStatus.CANCELLING)

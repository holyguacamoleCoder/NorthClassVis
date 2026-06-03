"""Tests for enriching trace steps with run metadata."""

from __future__ import annotations

import os
import sys

import pytest

_BACKEND_ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

from agent.runs.enrich import enrich_trace_and_timeline  # noqa: E402
from agent.runs.registry import RunRegistry  # noqa: E402


@pytest.fixture()
def isolated_agent_state(monkeypatch, tmp_path):
    root = tmp_path / ".agent"
    monkeypatch.setattr("agent.runs.registry.AGENT_STATE_DIR", root)
    monkeypatch.setattr("agent.common.paths.AGENT_STATE_DIR", root)
    return root


def test_enrich_trace_and_timeline_adds_run_id(isolated_agent_state):
    reg = RunRegistry()
    run_id = reg.begin_run(
        session_id="sess-x",
        tool_name="query_data",
        params={"resource": "submit_record", "class": "Class1"},
        job_id="job1",
        tool_call_id="call-abc",
    )
    reg.complete_run(run_id, result_ref="query-results/x.json")

    payload = {
        "trace": {
            "steps": [
                {
                    "tool": "query_data",
                    "call_id": "call-abc",
                    "params": {"resource": "submit_record"},
                    "summary": "ok",
                    "status": "ok",
                }
            ]
        },
        "timeline": [
            {
                "kind": "tool",
                "phase": "process",
                "step": {
                    "tool": "query_data",
                    "call_id": "call-abc",
                    "params": {"resource": "submit_record"},
                    "summary": "ok",
                    "status": "ok",
                },
            }
        ],
    }

    enriched = enrich_trace_and_timeline("sess-x", payload, reg, job_id="job1")
    step = enriched["trace"]["steps"][0]
    tl_step = enriched["timeline"][0]["step"]
    assert step["run_id"] == run_id
    assert tl_step["run_id"] == run_id

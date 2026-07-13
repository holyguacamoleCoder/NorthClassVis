"""Tests for job progress handler (subagent events)."""

from __future__ import annotations

import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from agent.http.progress import make_job_progress_handler, merge_progress_patch  # noqa: E402


def test_tool_end_does_not_crash_after_subagent_tool_events():
    """Regression: local import of build_tool_step must not shadow module import."""
    progress: dict = {"tool_steps": [], "timeline": []}
    handler = make_job_progress_handler(lambda patch: merge_progress_patch(progress, patch))

    handler({
        "type": "tool_start",
        "call_id": "c1",
        "tool": "run_subagent",
        "params": {"kind": "data_analyst", "task": "查 Class1"},
    })
    handler({
        "type": "subagent_tool_start",
        "call_id": "inner1",
        "tool": "query_data",
        "params": {"resource": "submit_record"},
    })
    handler({
        "type": "subagent_tool_end",
        "call_id": "inner1",
        "tool": "query_data",
        "params": {"resource": "submit_record"},
        "content": '{"rows": [], "meta": {"resource": "submit_record"}}',
    })
    handler({
        "type": "tool_end",
        "call_id": "c1",
        "tool": "run_subagent",
        "params": {"kind": "data_analyst", "task": "查 Class1"},
        "content": "[SubAgent data_analyst OK]\nturns: 2\nsummary:\nok\n",
    })

    assert len(progress["tool_steps"]) == 1
    step = progress["tool_steps"][0]
    assert step["kind"] == "subagent"
    assert step["tool"] == "run_subagent"
    assert progress.get("running_subagent") is None

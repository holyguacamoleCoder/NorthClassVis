"""Tests for turn_trace persistence (UI replay separate from messages)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from agent.session.turn_trace import (  # noqa: E402
    append_turn_trace,
    build_turn_trace_record,
    load_turn_traces,
)
from agent.session.store import FileSessionStore  # noqa: E402


def test_build_turn_trace_prefers_progress_steps(tmp_path):
    result = {
        "answer": "结论",
        "trace": {"steps": [{"tool": "query_data", "summary": "from messages"}]},
        "timeline": [],
    }
    progress = {
        "tool_steps": [
            {
                "tool": "run_subagent",
                "kind": "subagent",
                "summary": "数据侦察",
                "subagent": {"kind": "data_analyst", "inner_steps": [{"tool": "query_data"}]},
            }
        ],
        "timeline": [{"kind": "subagent", "phase": "process", "step": {"tool": "run_subagent"}}],
    }
    record = build_turn_trace_record(
        session_id="sess1",
        messages=[{"role": "user", "content": "查 Class1"}],
        result=result,
        progress=progress,
    )
    assert record["turn_index"] == 1
    assert record["trace"]["steps"][0]["tool"] == "run_subagent"
    assert record["trace"]["steps"][0]["subagent"]["inner_steps"]
    assert record["timeline"][0]["kind"] == "subagent"


def test_append_and_load_turn_traces(tmp_path):
    store = FileSessionStore(root=tmp_path / "sessions")
    sid = store.new_id()
    record = {
        "turn_index": 1,
        "session_id": sid,
        "trace": {"steps": [{"tool": "todo_write", "summary": "ok"}]},
        "timeline": [],
        "answer": "hi",
    }
    store.append_turn_trace(sid, record)
    loaded = store.load_turn_traces(sid)
    assert len(loaded) == 1
    assert loaded[0]["trace"]["steps"][0]["tool"] == "todo_write"

    record2 = {**record, "answer": "updated", "turn_index": 1}
    store.append_turn_trace(sid, record2)
    loaded2 = store.load_turn_traces(sid)
    assert len(loaded2) == 1
    assert loaded2[0]["answer"] == "updated"

    record3 = {**record, "turn_index": 2, "answer": "turn2"}
    store.append_turn_trace(sid, record3)
    loaded3 = store.load_turn_traces(sid)
    assert len(loaded3) == 2
    assert loaded3[1]["turn_index"] == 2

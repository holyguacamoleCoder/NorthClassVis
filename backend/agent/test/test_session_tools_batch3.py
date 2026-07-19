"""Batch-3 session tools: todo_write, compact, save_memory."""

import json
import sys
from pathlib import Path

import pytest

AGENT_ROOT = Path(__file__).resolve().parents[1]
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))

import runtime_bootstrap  # noqa: F401, E402

from loop import AgentLoop  # noqa: E402
from loop_state import LoopState  # noqa: E402
from permission import CapabilityMode, PermissionManager, filter_tools  # noqa: E402
from tools.definitions.manifest import MANIFEST, _MAX_TODO_ITEMS  # noqa: E402
from tools.definitions.schemas import TOOLS  # noqa: E402
from tools.handlers.compact import format_compact_applied_result, run_compact  # noqa: E402
from tools.handlers.todo_write import (  # noqa: E402
    export_todo_snapshot,
    reset_todo_state,
    run_todo_write,
)


def _tool(name: str):
    return next(d for d in MANIFEST if d.name == name)


def test_consult_excludes_session_tools():
    names = {t["function"]["name"] for t in filter_tools(TOOLS, CapabilityMode.CONSULT)}
    assert "todo_write" not in names
    assert "compact" not in names
    assert "memory" not in names
    assert "save_memory" not in names


def test_manifest_todo_write_batch3():
    todo = _tool("todo_write")
    items = todo.parameters["properties"]["items"]
    assert items["maxItems"] == _MAX_TODO_ITEMS
    assert "in_progress" in todo.description
    assert "consult" in todo.description.lower()
    assert "query_data" in todo.description


def test_manifest_compact_save_memory_batch3():
    compact = _tool("compact")
    assert "micro" in compact.description.lower() or "macro" in compact.description.lower()
    assert "Do NOT" in compact.description
    mem = _tool("memory")
    assert "Do NOT" in mem.description
    assert "add" in mem.description.lower()
    save = _tool("save_memory")
    assert "Do NOT" in save.description or "Prefer" in save.description


def test_todo_write_errors_and_header():
    reset_todo_state()
    out = run_todo_write(
        [
            {"content": "a", "status": "in_progress"},
            {"content": "b", "status": "in_progress"},
        ]
    )
    assert out.startswith("Error:")
    assert "in_progress" in out
    ok = run_todo_write([{"content": "query Class1", "status": "in_progress"}])
    assert ok.startswith("[Plan updated: 0/1 completed]")

    with_accept = run_todo_write(
        [
            {
                "content": "各专业学生数",
                "status": "in_progress",
                "acceptance": "count_distinct student_ID by major",
            }
        ]
    )
    assert "Acceptance:" in with_accept
    items, _ = export_todo_snapshot()
    assert items[0].get("acceptance") == "count_distinct student_ID by major"


def test_format_compact_applied_result():
    text = format_compact_applied_result(
        applied=True,
        messages_before=40,
        messages_after=5,
        tail_turns=3,
        focus="Class1",
        recent_files=["reports/a.md"],
    )
    assert "[Compact applied" in text
    assert "40" in text and "5" in text


def test_todo_only_folded_into_exploration_thrash():
    """todo_write-only batches are exploration_thrash (soft→hard), not a separate hard guard."""
    from loop_limits import EXPLORATION_THRASH_WINDOW

    loop = AgentLoop(LoopState(messages=[]))
    calls = [{"id": "1", "name": "todo_write", "arguments": json.dumps({"items": []})}]
    soft_ev = None
    for _ in range(EXPLORATION_THRASH_WINDOW):
        soft_ev = loop._detect_data_chain_oscillation(calls, [])
        if soft_ev is not None:
            break
    assert soft_ev is not None
    assert soft_ev.kind == "exploration_thrash"
    assert soft_ev.soft is True

    mixed = [
        {"id": "1", "name": "todo_write", "arguments": "{}"},
        {
            "id": "2",
            "name": "query_data",
            "arguments": json.dumps({"resource": "submit_record", "class": "Class1"}),
        },
    ]
    loop2 = AgentLoop(LoopState(messages=[]))
    assert loop2._detect_data_chain_oscillation(mixed, []) is None


def test_run_compact_placeholder():
    assert "pending" in run_compact(focus="keep scores").lower()

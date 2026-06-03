"""Tests for todo_write / load_skill tool step enrichment."""

from __future__ import annotations

import os
import sys

_BACKEND_ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

from agent.http.adapter import build_tool_step  # noqa: E402
from tools.handlers.todo_write import reset_todo_state, run_todo_write  # noqa: E402


def test_build_tool_step_todo_write():
    reset_todo_state()
    content = run_todo_write(
        [
            {"content": "inspect schema", "status": "completed"},
            {"content": "query data", "status": "in_progress", "active_form": "Running query"},
        ]
    )
    step = build_tool_step(
        "todo_write",
        {
            "items": [
                {"content": "inspect schema", "status": "completed"},
                {"content": "query data", "status": "in_progress"},
            ]
        },
        content,
        call_id="c1",
    )
    assert step["kind"] == "todo"
    assert step["todo_snapshot"]["completed"] == 1
    assert step["todo_snapshot"]["total"] == 2
    assert "1/2" in step["summary"]


def test_build_tool_step_load_skill():
    step = build_tool_step(
        "load_skill",
        {"name": "report-markdown"},
        '✅ Skill "report-markdown" 已加载\n\n<body>',
        call_id="c2",
    )
    assert step["kind"] == "skill"
    assert step["skill_name"] == "report-markdown"
    assert "report-markdown" in step["summary"]
    assert len(step["summary"]) < 80

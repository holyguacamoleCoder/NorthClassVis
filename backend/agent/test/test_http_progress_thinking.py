"""Job progress: thinking / thinking_delta events."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from agent.http.progress import (  # noqa: E402
    empty_job_progress,
    make_job_progress_handler,
    merge_progress_patch,
)


def test_empty_progress_includes_thinking():
    p = empty_job_progress()
    assert p["thinking"] == ""


def test_merge_thinking_delta():
    p = empty_job_progress()
    merge_progress_patch(p, {"phase": "thinking", "append_thinking": "理解"})
    merge_progress_patch(p, {"append_thinking": "问题"})
    assert p["thinking"] == "理解问题"
    assert p["phase"] == "thinking"


def test_answer_clears_thinking_when_requested():
    p = empty_job_progress()
    p["thinking"] = "重复"
    merge_progress_patch(
        p,
        {
            "phase": "answer",
            "answer": "最终",
            "thinking": "",
        },
    )
    assert p["answer"] == "最终"
    assert p["thinking"] == ""


def test_write_file_appends_report_links():
    progress = empty_job_progress()
    handler = make_job_progress_handler(lambda patch: merge_progress_patch(progress, patch))

    handler(
        {
            "type": "tool_end",
            "tool": "write_file",
            "params": {"path": "reports/demo.md"},
            "content": "[Write OK: path=reports/demo.md, bytes=100, created]",
        },
    )

    assert len(progress["report_links"]) == 1
    assert progress["report_links"][0]["path"] == "reports/demo.md"

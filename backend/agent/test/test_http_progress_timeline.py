"""Job progress: timeline append."""

from __future__ import annotations

import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from agent.http.progress import empty_job_progress, merge_progress_patch  # noqa: E402


def test_merge_timeline_append():
    p = empty_job_progress()
    merge_progress_patch(
        p,
        {
            "append_timeline": {"kind": "narration", "phase": "plan", "text": "计划"},
        },
    )
    assert len(p["timeline"]) == 1
    assert p["timeline"][0]["phase"] == "plan"


def test_merge_thinking_delta_appends_plan_narration():
    p = empty_job_progress()
    merge_progress_patch(p, {"append_thinking": "理解"})
    merge_progress_patch(p, {"append_thinking": "问题"})
    assert p["thinking"] == "理解问题"
    assert len(p["timeline"]) == 1
    assert p["timeline"][0]["text"] == "理解问题"

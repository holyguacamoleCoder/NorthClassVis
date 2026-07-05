"""Tests for write_file postprocess report validation."""

from __future__ import annotations

import json
from pathlib import Path

import runtime_bootstrap  # noqa: F401, E402

from loop_state import AnalysisToolContext
from tools.runtime.pipeline.postprocess import postprocess_tool_result

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "reports"


def test_postprocess_appends_report_validation(tmp_path, monkeypatch):
    from common.paths import DATA_DIR

    rel = "reports/student/J1/diagnosis.md"
    dest = DATA_DIR / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        (FIXTURES / "student_incomplete.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    tool_result = f"[Write OK: path={rel}, bytes=100]"
    ctx = AnalysisToolContext(session_id="sess-test")

    out = postprocess_tool_result(
        "write_file",
        tool_result,
        call_id="c1",
        parsed_args={"path": rel, "content": "x"},
        compact_state=None,
        analysis_context=ctx,
        batch_snapshots=[],
    )
    assert "[Report validate]" in out
    assert "missing required section" in out


def test_postprocess_registers_visual_links():
    payload = json.dumps(
        {"visual_links": [{"view": "WeekView", "params": {"student_ids": ["A"]}}]}
    )
    ctx = AnalysisToolContext()
    postprocess_tool_result(
        "build_visual_links",
        payload,
        call_id="c2",
        parsed_args={},
        compact_state=None,
        analysis_context=ctx,
        batch_snapshots=[],
    )
    assert len(ctx.session_visual_links) == 1
    assert ctx.session_visual_links[0]["view"] == "WeekView"

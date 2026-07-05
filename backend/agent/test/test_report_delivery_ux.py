"""Tests for report chart inject, tool status, and report write hints."""

from __future__ import annotations

import json

import runtime_bootstrap  # noqa: F401, E402

from agent.http.adapter import _tool_status, adapt_legacy_query_response
from hints.report_checks import append_report_write_checks, report_validation_failed
from report.inject import inject_report_charts_from_links
from report.validate import format_validation_for_tool_result


def test_inject_report_charts_from_session_links():
    md = "# R\n\n## evidence\n\n- x\n"
    links = [{"view": "WeekView", "params": {"student_ids": ["A"], "week_range": [1, 2]}}]
    new_md, notes = inject_report_charts_from_links(md, links)
    assert "report-chart" in new_md
    assert notes
    assert new_md.index("report-chart") < new_md.lower().index("## evidence")


def test_tool_status_detects_report_validate_errors():
    block = format_validation_for_tool_result(
        {"ok": False, "errors": ["missing section"], "warnings": [], "line_count": 1, "tier": "student", "sections": []}
    )
    assert _tool_status(f"[Write OK: path=reports/x.md]\n\n{block}") == "fail"


def test_tool_status_detects_edit_text_not_found():
    assert _tool_status("Error: Text not found in reports/a.md") == "fail"


def test_append_report_write_checks_adds_reminder():
    calls = [{"id": "c1", "name": "write_file"}]
    content = "[Write OK]\n\nError: Report validation failed.\n\n[Report validate]\nstatus: ERRORS\n  error: x"
    results = [{"tool_call_id": "c1", "content": content}]
    append_report_write_checks(calls, results)
    assert "<reminder>" in results[0]["content"]
    assert report_validation_failed(results[0]["content"])


def test_adapt_legacy_marks_unsatisfied_on_report_validate_errors():
    write_content = (
        "[Write OK: path=reports/student/A/diagnosis.md]\n\n"
        "Error: Report validation failed.\n\n[Report validate]\nstatus: ERRORS\n  error: missing"
    )
    messages = [
        {"role": "user", "content": "写报告"},
        {
            "role": "assistant",
            "tool_calls": [
                {
                    "id": "w1",
                    "type": "function",
                    "function": {"name": "write_file", "arguments": "{}"},
                }
            ],
        },
        {"role": "tool", "tool_call_id": "w1", "content": write_content},
        {"role": "assistant", "content": "报告写好了。"},
    ]
    out = adapt_legacy_query_response(messages)
    assert out["goal_check"]["is_satisfied"] is False
    assert out["summary"]["overall_status"] == "partial"

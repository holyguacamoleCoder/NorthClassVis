"""Tests for continue-report hints and section append edit."""

from __future__ import annotations

import runtime_bootstrap  # noqa: F401, E402

from hints.report_continue import (
    inject_report_continue_reminder,
    should_replace_report_false_completion,
)
from report.sections import append_section


def test_append_section_before_evidence():
    md = "## scope\na\n\n## summary\nb\n"
    out = append_section(md, "## limitations\nonly week 10-15")
    assert "## evidence" not in out.lower() or out.lower().index("## limitations") < out.lower().index("## evidence")
    assert "## limitations" in out


def test_inject_report_continue_reminder():
    messages = [
        {"role": "user", "content": "请继续把报告写完"},
        {
            "role": "tool",
            "content": "[Write OK: path=reports/student/A/diagnosis.md]",
        },
    ]
    assert inject_report_continue_reminder(messages, "请继续把报告写完") is True
    assert "<reminder>" in messages[0]["content"]
    assert "reports/student/A/diagnosis.md" in messages[0]["content"]


def test_should_replace_false_completion():
    turn = [
        {"role": "user", "content": "继续"},
        {
            "role": "tool",
            "content": "Error: Text not found in reports/student/A/diagnosis.md",
        },
    ]
    assert should_replace_report_false_completion(turn, produce_mode=True) is True
    turn_ok = turn + [
        {
            "role": "tool",
            "content": "[Edit OK]\n\n[Report validate: OK]",
        }
    ]
    assert should_replace_report_false_completion(turn_ok, produce_mode=True) is False

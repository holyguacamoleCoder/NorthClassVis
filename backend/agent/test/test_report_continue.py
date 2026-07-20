"""Tests for continue-report hints and section append edit."""

from __future__ import annotations

import runtime_bootstrap  # noqa: F401, E402

from hints.report_continue import (
    format_report_continue_hint,
    inject_report_continue_reminder,
    should_attach_report_continue_hint,
    should_replace_report_false_completion,
)
from report.sections import append_section
from session.turn_hints import build_turn_agent_hint
from session.ui_scope import compose_llm_user_content


def test_append_section_before_evidence():
    md = "## scope\na\n\n## summary\nb\n"
    out = append_section(md, "## limitations\nonly week 10-15")
    assert "## evidence" not in out.lower() or out.lower().index("## limitations") < out.lower().index("## evidence")
    assert "## limitations" in out


def test_report_continue_hint_via_turn_compose():
    """Reminder joins the *new* user turn; history messages stay untouched."""
    messages = [
        {"role": "user", "content": "请继续把报告写完"},
        {
            "role": "tool",
            "content": "[Write OK: path=reports/student/A/diagnosis.md]",
        },
    ]
    assert should_attach_report_continue_hint("请继续把报告写完")
    hint = build_turn_agent_hint(
        report_continue_path="reports/student/A/diagnosis.md",
        teacher_message="请继续把报告写完",
    )
    assert hint and "<reminder>" in hint
    assert "reports/student/A/diagnosis.md" in hint
    merged = compose_llm_user_content("请继续把报告写完", hint)
    assert "<reminder>" in merged
    # Deprecated injector must not rewrite history (prefix cache).
    assert inject_report_continue_reminder(messages, "请继续把报告写完") is False
    assert messages[0]["content"] == "请继续把报告写完"
    assert format_report_continue_hint("reports/student/A/diagnosis.md")


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

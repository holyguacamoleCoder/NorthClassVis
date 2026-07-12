"""Tests for revision-pass hint injection."""

from __future__ import annotations

import runtime_bootstrap  # noqa: F401, E402

from hints.report_revision import (
    append_report_revision_hint,
    should_suggest_revision_pass,
)


def test_should_suggest_when_full_coverage_not_ok():
    content = (
        "[Edit OK: path=reports/student/A/diagnosis.md]\n\n"
        "[Report validate]\nstatus: warn\n"
        "  coverage: 9/9\n"
        "  warn: section summary thin\n"
    )
    assert should_suggest_revision_pass(content) is True


def test_should_not_suggest_when_validate_ok():
    content = "[Edit OK]\n\n[Report validate: OK]"
    assert should_suggest_revision_pass(content) is False


def test_append_revision_hint_in_place():
    calls = [{"id": "c1", "name": "edit_file"}]
    results = [
        {
            "tool_call_id": "c1",
            "content": (
                "[Edit OK]\n\n[Report validate]\nstatus: warn\n  coverage: 8/8\n"
            ),
        }
    ]
    append_report_revision_hint(calls, results)
    assert "review_report" in results[0]["content"]
    assert "<reminder>" in results[0]["content"]

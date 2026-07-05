"""Tests for edit_file section replace and chart syntax normalize."""

from __future__ import annotations

from pathlib import Path

import runtime_bootstrap  # noqa: F401, E402

from report.normalize import fix_wrong_report_chart_syntax, find_wrong_report_chart_syntax
from report.sections import replace_section
from tools.handlers.base_tool import run_edit_file


SAMPLE = """# R

## Week Trend

old body line one
old body line two

## Evidence

- cite
"""


def test_fix_wrong_report_chart_image_syntax():
    raw = (
        '## Week Trend\n\n'
        '![趋势](<report-chart>{"view":"WeekView","params":{"student_ids":["A"],"week_range":[1,2]}})\n'
    )
    fixed, notes = fix_wrong_report_chart_syntax(raw)
    assert "```report-chart" in fixed
    assert "<report-chart>" not in fixed
    assert notes
    assert not find_wrong_report_chart_syntax(fixed)


def test_replace_section_by_heading_case_insensitive():
    new = "## week_trend\n\nnew body\n"
    out = replace_section(SAMPLE, "## Week Trend", new)
    assert out is not None
    assert "new body" in out
    assert "old body line one" not in out
    assert "## Evidence" in out


def test_edit_file_section_replace_mode(tmp_path, monkeypatch):
    from common.paths import DATA_DIR

    rel = "reports/student/T1/diagnosis.md"
    dest = DATA_DIR / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(SAMPLE, encoding="utf-8")

    result = run_edit_file(
        rel,
        "## Week Trend\n\nthis body does not exist in file",
        "## Week Trend\n\nreplaced whole section\n",
    )
    assert "Edit OK" in result
    assert "section_replace" in result
    text = dest.read_text(encoding="utf-8")
    assert "replaced whole section" in text
    assert "old body line one" not in text


def test_edit_file_failure_includes_hint(tmp_path, monkeypatch):
    from common.paths import DATA_DIR

    rel = "reports/student/T2/diagnosis.md"
    dest = DATA_DIR / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(SAMPLE, encoding="utf-8")

    result = run_edit_file(rel, "totally missing snippet", "x")
    assert "Text not found" in result
    assert "[Edit hint]" in result
    assert "Week Trend" in result

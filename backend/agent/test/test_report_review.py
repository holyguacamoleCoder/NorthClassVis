"""Tests for review_report cross-section consistency."""

from __future__ import annotations

from pathlib import Path

import runtime_bootstrap  # noqa: F401, E402

from report.review import format_review_for_tool_result, review_report
from tools.handlers.report_tools import run_review_report

FIXTURE_OK = Path(__file__).resolve().parent / "fixtures" / "reports" / "student_minimal_ok.md"


def _load_fixture() -> str:
    return FIXTURE_OK.read_text(encoding="utf-8")


def test_review_report_ok_fixture():
    text = _load_fixture()
    result = review_report(
        text,
        path="reports/student/J23517/diagnosis.md",
        tier="student",
        validation_level="deliver",
    )
    assert result.tier == "student"
    blocking = [i for i in result.issues if i.severity == "error"]
    assert not blocking
    formatted = format_review_for_tool_result(result)
    assert "[Report review]" in formatted
    assert "path:" in formatted


def test_review_detects_summary_week_trend_mismatch():
    text = _load_fixture()
    text = text.replace(
        "## summary\n\n近三周 peak 均值呈下降趋势",
        "## summary\n\n近三周 peak 均值呈上升趋势",
    )
    result = review_report(
        text,
        path="reports/student/J23517/diagnosis.md",
        tier="student",
    )
    assert any("summary" in (i.section or "") for i in result.issues)
    assert any("week_trend" in i.issue for i in result.issues)
    assert result.status == "needs_revision"


def test_review_detects_placeholder():
    text = _load_fixture()
    text = text.replace("J23517", "学生ID")
    result = review_report(
        text,
        path="reports/student/TODO/diagnosis.md",
        tier="student",
    )
    assert any(i.severity == "error" for i in result.issues)
    assert any("占位" in i.issue for i in result.issues)


def test_review_detects_scope_chart_mismatch():
    text = _load_fixture()
    text = text.replace('"J23517"', '"OTHER_STUDENT"')
    result = review_report(
        text,
        path="reports/student/J23517/diagnosis.md",
        tier="student",
    )
    assert any("WeekView" in i.issue for i in result.issues)
    assert result.status == "needs_revision"


def test_review_detects_actions_orphan_question():
    text = _load_fixture()
    text = text.replace(
        "针对链表知识点安排一次小测",
        "针对 Question_ORPHAN 安排一次小测",
    )
    result = review_report(
        text,
        path="reports/student/J23517/diagnosis.md",
        tier="student",
    )
    assert any(i.section == "actions" for i in result.issues)
    assert any("Question_ORPHAN" in i.issue for i in result.issues)


def test_run_review_report_tool(tmp_path, monkeypatch):
    import tools.handlers.base_tool as bt

    monkeypatch.setattr(bt, "DATA_DIR", tmp_path)
    rel = "reports/student/A/diagnosis.md"
    dest = tmp_path / rel
    dest.parent.mkdir(parents=True)
    dest.write_text(_load_fixture(), encoding="utf-8")

    out = run_review_report(rel)
    assert "[Report review]" in out
    assert "reports/student/A/diagnosis.md" in out


def test_run_review_report_rejects_non_reports(tmp_path, monkeypatch):
    import tools.handlers.base_tool as bt

    monkeypatch.setattr(bt, "DATA_DIR", tmp_path)
    out = run_review_report("exports/foo.md")
    assert out.startswith("Error:")

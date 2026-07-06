"""Tests for report final delivery check."""

from __future__ import annotations

from pathlib import Path

import runtime_bootstrap  # noqa: F401, E402

from report.charts import extract_chart_blocks
from report.finalize import dedupe_report_sections, finalize_report_file, finalize_report_markdown


def test_dedupe_report_sections_keeps_first():
    md = """# T

## scope
first

## summary
a

## scope
duplicate

## evidence
e
"""
    fixed, notes = dedupe_report_sections(md)
    assert notes
    assert fixed.count("## scope") == 1
    assert "first" in fixed
    assert "duplicate" not in fixed


def test_finalize_markdown_dedupes_extra_weekview():
    md = """# R

## week_trend

```report-chart
{"view": "WeekView", "params": {"student_ids": ["A"], "week_range": [1, 5]}}
```

## question_anchors

```report-chart
{"view": "WeekView", "params": {"week_range": [1, 5]}}
```

```report-chart
{"view": "QuestionView", "params": {"title_ids": ["Q1"]}}
```
"""
    out = finalize_report_markdown(md, path="reports/student/A/diagnosis.md")
    blocks = extract_chart_blocks(out["normalized_text"])
    week = [b for b in blocks if b.view == "WeekView" and not b.error]
    assert len(week) == 1
    assert week[0].params.get("student_ids") == ["A"]


def test_finalize_report_file_writes_back(tmp_path, monkeypatch):
    from common.paths import DATA_DIR

    rel = "reports/student/T1/diagnosis.md"
    dest = DATA_DIR / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        "# R\n\n## week_trend\n\n"
        '```report-chart\n{"view":"WeekView","params":{"student_ids":["A"],"week_range":[1,2]}}\n```\n\n'
        "## evidence\n\n"
        '```report-chart\n{"view":"WeekView","params":{"week_range":[1,2]}}\n```\n',
        encoding="utf-8",
    )
    result = finalize_report_file(rel, write_back=True)
    assert result["fixes"]
    text = dest.read_text(encoding="utf-8")
    assert text.count("WeekView") == 1

"""WeekView student_id enrichment and report-chart patching."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import runtime_bootstrap  # noqa: F401

AGENT_ROOT = Path(__file__).resolve().parents[1]
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))

from data.filter_context import clean_student_ids, is_placeholder_student_id  # noqa: E402
from data.visual_links import normalize_week_params  # noqa: E402
from report.charts import sync_report_chart_week_view_params  # noqa: E402
from report.finalize import normalize_report_deliverable  # noqa: E402


def test_clean_student_ids_rejects_placeholders():
    assert is_placeholder_student_id("student1")
    assert is_placeholder_student_id("代表学生ID1")
    clean = clean_student_ids(["student1", "6ae7d356ba998218af82"])
    assert clean == ["6ae7d356ba998218af82"]


def test_normalize_week_params_keeps_valid_student_ids():
    out, err = normalize_week_params(
        {
            "week_range": [13, 15],
            "student_ids": ["student1", "79fdbcf16db75f75383a"],
        }
    )
    assert err is None
    assert out is not None
    assert out.get("student_ids") == ["79fdbcf16db75f75383a"]
    assert out.get("week_range") == [13, 15]


def test_sync_report_chart_week_view_params(monkeypatch):
    repo_root = AGENT_ROOT.parent.parent
    monkeypatch.chdir(repo_root)
    from data.filter_context import FilterContext
    from tools.handlers.context_tools import run_build_visual_links

    fc = FilterContext(classes=("Class2",), week_range=(13, 15), source="http_body")
    raw = run_build_visual_links(
        links=[{"view": "WeekView", "params": {"week_range": [13, 15]}}],
        _filter_context=fc,
    )
    links = json.loads(raw)["visual_links"]
    md = """## week_trend

```report-chart
{
  "view": "WeekView",
  "params": {
    "student_ids": ["student1", "student2"],
    "week_range": [13, 15]
  }
}
```
"""
    patched, notes = sync_report_chart_week_view_params(md, links)
    assert any("patched" in n for n in notes)
    assert "student1" not in patched
    ids = links[0]["params"]["student_ids"]
    assert ids[0] in patched

    normalized, fix_notes = normalize_report_deliverable(
        md,
        session_visual_links=links,
        inject_missing_charts=False,
    )
    assert "student1" not in normalized
    assert any("patched" in n for n in fix_notes)


def test_sync_report_chart_from_filter_context_without_visual_links(monkeypatch):
    repo_root = AGENT_ROOT.parent.parent
    monkeypatch.chdir(repo_root)
    from data.filter_context import FilterContext

    fc = FilterContext(classes=("Class2",), week_range=(13, 15), source="http_body")
    md = """## week_trend

```report-chart
{
  "view": "WeekView",
  "params": {
    "week_range": [13, 15],
    "student_ids": ["代表学生ID1", "代表学生ID2"]
  }
}
```
"""
    patched, notes = sync_report_chart_week_view_params(md, None, fc)
    assert any("filter_context" in n for n in notes)
    assert "代表学生ID1" not in patched
    assert "79fdbcf16db75f75383a" in patched or "6ae7d356ba998218af82" in patched

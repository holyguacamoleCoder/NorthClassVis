import json
import sys
from pathlib import Path

import runtime_bootstrap  # noqa: F401, E402

AGENT_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = AGENT_ROOT / "test" / "fixtures" / "reports"

from report.charts import extract_chart_blocks, validate_report_charts
from report.evidence_cites import extract_evidence_cites
from report.parse import infer_tier_from_path, parse_report_markdown
from report.validate import format_validation_for_tool_result, validate_report


def test_infer_tier_from_path():
    assert infer_tier_from_path("reports/student/J23517/diagnosis.md") == "student"
    assert infer_tier_from_path("reports/class/Class2/overview.md") == "class"
    assert infer_tier_from_path("reports/notes/weekly.md") == "freeform"


def test_parse_report_sections():
    text = (FIXTURES / "student_minimal_ok.md").read_text(encoding="utf-8")
    parsed = parse_report_markdown(text)
    ids = [s.id for s in parsed.sections]
    assert "week_trend" in ids
    assert "evidence" in ids
    week = parsed.section_map()["week_trend"]
    assert week.line_count >= 5
    assert week.table_rows == 0


def test_parse_chinese_section_aliases():
    md = """# R

## 范围
班级 Class2

## 摘要
整体良好

## 班级趋势
上升

## 问题类型
Q1

## 评分分布
差异

## 行动建议
辅导

## 证据
[@ref:query-results/x.json]

## 限制因素
仅三周
"""
    parsed = parse_report_markdown(md)
    ids = {s.id for s in parsed.sections}
    assert "scope" in ids
    assert "summary" in ids
    assert "week_trend" in ids
    assert "question_anchors" in ids
    assert "distribution" in ids
    assert "actions" in ids
    assert "evidence" in ids
    assert "limitations" in ids
    result = validate_report(md, tier="class")
    assert "missing required section" not in str(result.get("errors"))


def test_extract_chart_blocks():
    text = (FIXTURES / "student_minimal_ok.md").read_text(encoding="utf-8")
    blocks = extract_chart_blocks(text)
    assert len(blocks) == 2
    views = {b.view for b in blocks}
    assert views == {"WeekView", "QuestionView"}


def test_validate_charts_rejects_student_view_fence():
    body = '```report-chart\n{"view":"StudentView","params":{"student_ids":["A"]}}\n```'
    result = validate_report_charts(body)
    assert any("StudentView" in e for e in result.errors)


def test_extract_evidence_cites():
    text = (FIXTURES / "student_minimal_ok.md").read_text(encoding="utf-8")
    cites = extract_evidence_cites(text)
    kinds = {c.kind for c in cites}
    assert "ref" in kinds


def test_legacy_markdown_link_in_evidence_fails():
    text = (FIXTURES / "student_minimal_ok.md").read_text(encoding="utf-8")
    text = text.replace(
        "[@ref:query-results/week-trend.json]",
        "[周趋势](query-results/week-trend.json)",
    )
    result = validate_report(text, tier="student")
    assert result["ok"] is False
    assert any("markdown link" in e for e in result["errors"])


def test_unknown_ref_cite_is_warning_in_deliver():
    text = (FIXTURES / "student_minimal_ok.md").read_text(encoding="utf-8")
    from loop_state import AnalysisToolContext, QuerySnapshot

    ctx = AnalysisToolContext(session_id="s1")
    ctx.turn_snapshots = [
        QuerySnapshot(
            dataset_id="ds_known",
            result_ref="query-results/known.json",
            resource="week_aggregation",
            result_rows=10,
        )
    ]
    result = validate_report(
        text, tier="student", analysis_context=ctx, validation_level="deliver"
    )
    assert not any("result_ref not in session catalog" in e for e in result["errors"])
    assert any("result_ref not in session catalog" in w for w in result["warnings"])


def test_unknown_ref_cite_is_error_in_strict():
    text = (FIXTURES / "student_minimal_ok.md").read_text(encoding="utf-8")
    from loop_state import AnalysisToolContext, QuerySnapshot

    ctx = AnalysisToolContext(session_id="s1")
    ctx.turn_snapshots = [
        QuerySnapshot(
            dataset_id="ds_known",
            result_ref="query-results/known.json",
            resource="week_aggregation",
            result_rows=10,
        )
    ]
    result = validate_report(
        text, tier="student", analysis_context=ctx, validation_level="strict"
    )
    assert any("result_ref not in session catalog" in e for e in result["errors"])


def test_collect_evidence_sources_includes_legacy_links():
    from report.evidence_cites import collect_evidence_sources

    body = "- 数据 [成绩](query-results/abc.json)\n- 标签 [@ref:query-results/def.json]"
    sources = collect_evidence_sources(body)
    targets = {c.target for c in sources}
    assert "query-results/abc.json" in targets
    assert "query-results/def.json" in targets


def test_chart_fence_trailing_prose_errors():
    body = (
        '```report-chart\n'
        '{"view":"WeekView","params":{"student_ids":["A"],"week_range":[1,5]}}\n'
        '图表说明文字\n'
        '```'
    )
    result = validate_report_charts(body)
    assert any("trailing text" in e for e in result.errors)


def test_repair_report_chart_fences_moves_trailing_prose():
    from report.charts import repair_report_chart_fences

    body = (
        "## week_trend\n\n"
        '```report-chart\n'
        '{"view":"WeekView","params":{"student_ids":["A"],"week_range":[1,5]}}\n'
        '图表说明\n'
        '```\n'
    )
    fixed, notes = repair_report_chart_fences(body)
    assert notes
    assert "图表说明" in fixed
    assert fixed.index("```") < fixed.index("图表说明")
    result = validate_report_charts(fixed)
    assert not result.errors


def test_dedupe_report_chart_fences_keeps_richest_weekview():
    from report.charts import dedupe_report_chart_fences

    body = (
        '```report-chart\n{"view":"WeekView","params":{"week_range":[1,5]}}\n```\n\n'
        '```report-chart\n'
        '{"view":"WeekView","params":{"student_ids":["J1"],"week_range":[1,5]}}\n```\n'
    )
    fixed, notes = dedupe_report_chart_fences(body)
    assert notes
    blocks = extract_chart_blocks(fixed)
    week_blocks = [b for b in blocks if b.view == "WeekView" and not b.error]
    assert len(week_blocks) == 1
    assert week_blocks[0].params.get("student_ids") == ["J1"]


def test_validate_student_minimal_ok():
    text = (FIXTURES / "student_minimal_ok.md").read_text(encoding="utf-8")
    result = validate_report(
        text,
        tier="student",
        path="reports/student/J23517/diagnosis.md",
    )
    assert result["ok"] is True
    assert not result["errors"]
    assert result["line_count"] >= 40


def test_validate_student_incomplete_fails():
    text = (FIXTURES / "student_incomplete.md").read_text(encoding="utf-8")
    result = validate_report(text, tier="student")
    assert result["ok"] is False
    missing = result["missing_sections"]
    assert "week_trend" in missing
    assert "student_structure" in missing


def test_format_validation_for_tool_result():
    block = format_validation_for_tool_result(
        {"ok": False, "tier": "student", "line_count": 10, "sections": [], "errors": ["x"], "warnings": []}
    )
    assert block.startswith("Error: Report validation failed")
    assert "[Report validate]" in block
    assert "error: x" in block


def test_cli_json_roundtrip(tmp_path):
    src = FIXTURES / "student_minimal_ok.md"
    dest = tmp_path / "copy.md"
    dest.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    result = validate_report(dest.read_text(encoding="utf-8"), tier="student", path=dest)
    payload = json.loads(json.dumps(result, ensure_ascii=False))
    assert payload["tier"] == "student"


def test_parse_h4_numbered_english_sections():
    md = """### Class2 本学期概况

#### 1. Scope
班级 Class2 概况说明。

#### 2. Summary
整体良好。

#### 3. Week Trend
周趋势上升。

#### 4. Question Anchors
题型 Q1。

#### 5. Distribution
分布较均衡。

#### 6. Actions
加强辅导。

#### 7. Evidence
[@ref:query-results/week.json]

#### 8. Limitations
仅三周数据。
"""
    parsed = parse_report_markdown(md)
    ids = {s.id for s in parsed.sections}
    assert "scope" in ids
    assert "week_trend" in ids
    assert "limitations" in ids
    assert len(parsed.sections) == 8


def test_deliver_allows_partial_section_coverage():
    md = """## scope
a

## summary
b

## week_trend
c

## question_anchors
d

## distribution
e

## actions
f

## evidence
[@ref:query-results/x.json]

## limitations
g
"""
    # Drop two sections for 6/8 coverage
    md_partial = md.replace("## distribution\ne\n\n", "").replace("## actions\nf\n\n", "")
    result = validate_report(md_partial, tier="class", validation_level="deliver")
    assert result["ok"] is True
    assert result["section_coverage"]["present"] == 6


def test_draft_demotes_missing_sections_to_warnings():
    text = (FIXTURES / "student_incomplete.md").read_text(encoding="utf-8")
    result = validate_report(text, tier="student", validation_level="draft")
    assert not any("missing required section" in e for e in result["errors"])
    assert result["ok"] is True or not result["errors"]


def test_normalize_report_headings_promotes_h4():
    from report.headings import normalize_report_headings

    md = """### Title

#### 1. Scope
body scope

#### 2. Summary
body summary
"""
    fixed, notes = normalize_report_headings(md)
    assert notes
    assert "## scope" in fixed
    assert "## summary" in fixed
    assert "####" not in fixed

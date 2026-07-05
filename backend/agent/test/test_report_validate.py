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
    assert block.startswith("[Report validate]")
    assert "error: x" in block


def test_cli_json_roundtrip(tmp_path):
    src = FIXTURES / "student_minimal_ok.md"
    dest = tmp_path / "copy.md"
    dest.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    result = validate_report(dest.read_text(encoding="utf-8"), tier="student", path=dest)
    payload = json.loads(json.dumps(result, ensure_ascii=False))
    assert payload["tier"] == "student"

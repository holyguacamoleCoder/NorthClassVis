from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from loop_state import AnalysisToolContext

from .charts import (
    check_chart_explanations,
    validate_charts_against_session,
    validate_report_charts,
)
from .digest import known_ids_from_context, validate_cites_against_session
from .evidence_cites import extract_evidence_cites, validate_evidence_section
from .parse import (
    infer_tier_from_path,
    load_quality_rules,
    parse_report_markdown,
)


def validate_report(
    source: str,
    *,
    tier: str | None = None,
    path: str | Path | None = None,
    rules_path: Path | None = None,
    require_evidence_cites: bool = False,
    analysis_context: AnalysisToolContext | None = None,
    session_visual_links: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Validate report markdown; returns JSON-serializable result."""
    resolved_tier = (tier or "").strip().lower()
    if not resolved_tier and path is not None:
        resolved_tier = infer_tier_from_path(path)
    if not resolved_tier:
        resolved_tier = "freeform"

    rules_doc = load_quality_rules(rules_path)
    tiers = rules_doc.get("tiers") or {}
    tier_rules = tiers.get(resolved_tier)
    if not tier_rules:
        return {
            "ok": False,
            "tier": resolved_tier,
            "errors": [f"unknown tier {resolved_tier!r}"],
            "warnings": [],
        }

    parsed = parse_report_markdown(source)
    section_map = parsed.section_map()
    errors: list[str] = []
    warnings: list[str] = []

    min_total = int(tier_rules.get("min_total_lines") or 0)
    if min_total and parsed.total_lines < min_total:
        warnings.append(
            f"total lines {parsed.total_lines} < tier minimum {min_total}"
        )

    required = [str(s) for s in (tier_rules.get("required_sections") or [])]
    missing = [sid for sid in required if sid not in section_map]
    for sid in missing:
        errors.append(f"missing required section: ## {sid}")

    present_ids = [s.id for s in parsed.sections]
    expected_order = [sid for sid in required if sid in present_ids]
    ordered_present = [sid for sid in present_ids if sid in required]
    if ordered_present != expected_order:
        warnings.append(
            f"sections out of recommended order (expected {expected_order}, got {ordered_present})"
        )

    for section in parsed.sections:
        if section.line_count == 0 and section.id not in missing:
            warnings.append(f"section {section.id} is empty (use edit_file to fill)")

    section_specs: dict[str, Any] = tier_rules.get("sections") or {}
    for sid, spec in section_specs.items():
        if not isinstance(spec, dict):
            continue
        section = section_map.get(sid)
        if section is None:
            continue
        min_lines = int(spec.get("min_lines") or 0)
        if min_lines and section.line_count < min_lines:
            warnings.append(
                f"section {sid}: {section.line_count} lines < minimum {min_lines}"
            )
        min_rows = int(spec.get("min_table_rows") or 0)
        if min_rows and section.table_rows < min_rows:
            warnings.append(
                f"section {sid}: {section.table_rows} table rows < minimum {min_rows}"
            )
        required_views = spec.get("require_chart_views") or []
        if required_views:
            chart_result = validate_report_charts(section.body)
            views_present = {b.view for b in chart_result.blocks if b.view and not b.error}
            for view in required_views:
                if view not in views_present:
                    warnings.append(f"section {sid}: expected report-chart for {view}")

    chart_validation = validate_report_charts(source)
    errors.extend(chart_validation.errors)
    warnings.extend(chart_validation.warnings)

    links = session_visual_links
    if links is None and analysis_context is not None:
        links = analysis_context.session_visual_links
    warnings.extend(validate_charts_against_session(source, links))
    warnings.extend(check_chart_explanations(source))

    known_ds, known_refs = known_ids_from_context(analysis_context)
    all_cites = extract_evidence_cites(source)
    cite_errors, cite_warnings = validate_cites_against_session(
        all_cites,
        known_dataset_ids=known_ds,
        known_result_refs=known_refs,
    )
    errors.extend(cite_errors)
    warnings.extend(cite_warnings)

    evidence_section = section_map.get("evidence")
    if evidence_section:
        cite_validation = validate_evidence_section(
            evidence_section.body,
            require_at_least_one_cite=require_evidence_cites,
        )
        errors.extend(cite_validation.errors)
        warnings.extend(cite_validation.warnings)
    elif "evidence" in required:
        pass

    sections_out = [
        {
            "id": s.id,
            "title": s.title,
            "line_count": s.line_count,
            "table_rows": s.table_rows,
        }
        for s in parsed.sections
    ]

    charts_out = [
        {
            "index": b.index,
            "view": b.view,
            "params": b.params,
            "error": b.error,
        }
        for b in chart_validation.blocks
    ]

    ok = not errors
    return {
        "ok": ok,
        "tier": resolved_tier,
        "line_count": parsed.total_lines,
        "sections": sections_out,
        "missing_sections": missing,
        "charts": charts_out,
        "errors": errors,
        "warnings": warnings,
    }


def format_validation_for_tool_result(result: dict[str, Any]) -> str:
    """Short block to append to write_file / edit_file tool results."""
    if result.get("ok") and not result.get("warnings"):
        return "[Report validate: OK]"
    lines = ["[Report validate]"]
    if not result.get("ok"):
        lines.append("status: ERRORS")
    elif result.get("warnings"):
        lines.append("status: OK with warnings")
    for err in result.get("errors") or []:
        lines.append(f"  error: {err}")
    for warn in result.get("warnings") or []:
        lines.append(f"  warn: {warn}")
    lines.append(
        f"  lines={result.get('line_count')} tier={result.get('tier')} "
        f"sections={len(result.get('sections') or [])}"
    )
    return "\n".join(lines)


def validate_report_file(
    file_path: str | Path,
    *,
    tier: str | None = None,
    analysis_context: AnalysisToolContext | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    path = Path(file_path)
    text = path.read_text(encoding="utf-8")
    return validate_report(
        text,
        tier=tier,
        path=path,
        analysis_context=analysis_context,
        **kwargs,
    )

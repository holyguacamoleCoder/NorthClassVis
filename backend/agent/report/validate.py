from __future__ import annotations

from pathlib import Path
from typing import Any

from loop_state import AnalysisToolContext

from .charts import (
    check_chart_explanations,
    validate_charts_against_session,
    validate_report_charts,
)
from .digest import known_ids_from_context, validate_cites_against_session
from .evidence_cites import collect_evidence_sources, validate_evidence_section
from .parse import (
    infer_tier_from_path,
    load_quality_rules,
    load_validation_level_config,
    parse_report_markdown,
)

VALIDATION_LEVELS = frozenset({"draft", "deliver", "strict"})


def _resolve_validation_level(level: str | None) -> str:
    resolved = (level or "deliver").strip().lower()
    return resolved if resolved in VALIDATION_LEVELS else "deliver"


def _min_section_coverage_ratio(
    tier_rules: dict[str, Any],
    global_rules: dict[str, Any],
    *,
    level: str,
) -> float:
    if level == "strict":
        return 1.0
    tier_ratio = tier_rules.get("min_section_coverage_ratio")
    if tier_ratio is not None:
        return float(tier_ratio)
    global_ratio = global_rules.get("default_min_section_coverage_ratio")
    if global_ratio is not None:
        return float(global_ratio)
    return 0.75


def _delivery_status(ok: bool, warnings: list[str]) -> str:
    if not ok:
        return "fail"
    if warnings:
        return "warn"
    return "pass"


def validate_report(
    source: str,
    *,
    tier: str | None = None,
    path: str | Path | None = None,
    rules_path: Path | None = None,
    require_evidence_cites: bool = False,
    validation_level: str | None = None,
    analysis_context: AnalysisToolContext | None = None,
    session_visual_links: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Validate report markdown; returns JSON-serializable result."""
    level = _resolve_validation_level(validation_level)
    level_cfg = load_validation_level_config(level, rules_path=rules_path)

    resolved_tier = (tier or "").strip().lower()
    if not resolved_tier and path is not None:
        resolved_tier = infer_tier_from_path(path)
    if not resolved_tier:
        resolved_tier = "freeform"

    rules_doc = load_quality_rules(rules_path)
    global_rules = rules_doc.get("global") or {}
    if not require_evidence_cites:
        require_evidence_cites = bool(global_rules.get("require_evidence_cites"))
    tiers = rules_doc.get("tiers") or {}
    tier_rules = tiers.get(resolved_tier)
    if not tier_rules:
        return {
            "ok": False,
            "tier": resolved_tier,
            "validation_level": level,
            "delivery_status": "fail",
            "errors": [f"unknown tier {resolved_tier!r}"],
            "warnings": [],
        }

    parsed = parse_report_markdown(source, rules_path=rules_path)
    section_map = parsed.section_map()
    errors: list[str] = []
    warnings: list[str] = []

    min_total = int(tier_rules.get("min_total_lines") or 0)
    if min_total and parsed.total_lines < min_total:
        warnings.append(
            f"total lines {parsed.total_lines} < tier minimum {min_total}"
        )

    required = [str(s) for s in (tier_rules.get("required_sections") or [])]
    present_required = [sid for sid in required if sid in section_map]
    missing = [sid for sid in required if sid not in section_map]
    coverage_ratio = (
        len(present_required) / len(required) if required else 1.0
    )
    min_coverage = _min_section_coverage_ratio(tier_rules, global_rules, level=level)

    if coverage_ratio < min_coverage:
        msg = (
            f"section coverage {len(present_required)}/{len(required)} "
            f"below minimum {min_coverage:.0%}"
        )
        if level in ("deliver", "strict"):
            errors.append(msg)
        else:
            warnings.append(msg)
    elif level == "strict":
        for sid in missing:
            errors.append(f"missing required section: ## {sid}")
    elif missing:
        warnings.append(f"missing sections: {', '.join(missing)}")

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
            views_present = {
                b.view for b in chart_result.blocks if b.view and not b.error
            }
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
    all_cites = collect_evidence_sources(source)
    if analysis_context is not None and (known_ds or known_refs or all_cites):
        cite_errors, cite_warnings = validate_cites_against_session(
            all_cites,
            known_dataset_ids=known_ds,
            known_result_refs=known_refs,
            validation_level=level,
        )
        errors.extend(cite_errors)
        warnings.extend(cite_warnings)

    evidence_section = section_map.get("evidence")
    if evidence_section:
        cite_validation = validate_evidence_section(
            evidence_section.body,
            require_at_least_one_cite=require_evidence_cites,
        )
        if level == "draft":
            for err in cite_validation.errors:
                if "markdown link" in err or "cite tag" in err or "empty" in err:
                    warnings.append(err)
                else:
                    warnings.append(err)
        else:
            errors.extend(cite_validation.errors)
        warnings.extend(cite_validation.warnings)
    elif "evidence" in required and level in ("deliver", "strict"):
        if require_evidence_cites:
            errors.append("missing required section: ## evidence")

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

    if level == "draft":
        # Draft gate: only chart blockers; demote structural/cite errors to warnings.
        structural = errors[:]
        errors = [e for e in structural if _is_chart_blocker(e)]
        for err in structural:
            if err not in errors:
                warnings.append(err)

    ok = not errors
    return {
        "ok": ok,
        "tier": resolved_tier,
        "validation_level": level,
        "delivery_status": _delivery_status(ok, warnings),
        "line_count": parsed.total_lines,
        "sections": sections_out,
        "missing_sections": missing,
        "section_coverage": {
            "present": len(present_required),
            "required": len(required),
            "ratio": coverage_ratio,
            "min_ratio": min_coverage,
        },
        "charts": charts_out,
        "errors": errors,
        "warnings": warnings,
        "level_config": level_cfg,
    }


def _is_chart_blocker(message: str) -> bool:
    lower = message.lower()
    needles = (
        "report-chart",
        "chart",
        "weekview",
        "json",
        "trailing text",
        "studentview",
        "forbid",
    )
    return any(n in lower for n in needles)


def format_validation_for_tool_result(result: dict[str, Any]) -> str:
    """Short block to append to write_file / edit_file tool results."""
    errors = result.get("errors") or []
    warnings = result.get("warnings") or []
    if result.get("ok") and not warnings:
        return "[Report validate: OK]"
    lines = ["[Report validate]"]
    status = result.get("delivery_status")
    if status:
        lines.append(f"status: {status}")
    elif not result.get("ok"):
        lines.append("status: fail")
    elif warnings:
        lines.append("status: warn")
    coverage = result.get("section_coverage") or {}
    if coverage.get("required"):
        lines.append(
            f"  coverage: {coverage.get('present')}/{coverage.get('required')}"
        )
    for err in errors[:3]:
        lines.append(f"  error: {err}")
    if len(errors) > 3:
        lines.append(f"  error: … +{len(errors) - 3} more")
    for warn in warnings[:3]:
        lines.append(f"  warn: {warn}")
    if len(warnings) > 3:
        lines.append(f"  warn: … +{len(warnings) - 3} more")
    lines.append(
        f"  lines={result.get('line_count')} tier={result.get('tier')} "
        f"sections={len(result.get('sections') or [])} "
        f"level={result.get('validation_level') or 'deliver'}"
    )
    block = "\n".join(lines)
    if errors:
        block = (
            "Error: Report validation failed. "
            f"{len(errors)} error(s). Use edit_file to fix before telling the teacher the report is done.\n\n"
            + block
        )
    return block


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

"""Normalize and validate report deliverables before teacher-facing HTTP response."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from loop_state import AnalysisToolContext, QuerySnapshot

from .charts import (
    dedupe_report_chart_fences,
    repair_report_chart_fences,
    sync_report_chart_week_view_params,
)
from .headings import normalize_report_headings
from .inject import inject_report_charts_from_links
from .normalize import fix_wrong_report_chart_syntax
from .parse import infer_tier_from_path
from .validate import format_validation_for_tool_result, validate_report


def dedupe_report_sections(source: str) -> tuple[str, list[str]]:
    """Keep the first ## section per normalized id; drop accidental duplicates."""
    from .parse import (
        _SECTION_RE,
        load_canonical_section_ids,
        load_section_aliases,
        resolve_section_id,
    )

    text = source or ""
    matches = list(_SECTION_RE.finditer(text))
    if not matches:
        return source, []

    aliases = load_section_aliases()
    canonical = load_canonical_section_ids()

    first_idx: int | None = None
    for idx, match in enumerate(matches):
        sid = resolve_section_id(match.group(2).strip(), aliases=aliases)
        if sid in canonical:
            first_idx = idx
            break
    if first_idx is None:
        return source, []

    seen: set[str] = set()
    kept_chunks: list[str] = []
    removed = 0
    preamble = text[: matches[first_idx].start()].strip()

    for idx in range(first_idx, len(matches)):
        match = matches[idx]
        title = match.group(2).strip()
        sid = resolve_section_id(title, aliases=aliases)
        if sid not in canonical:
            continue
        start = match.start()
        end = len(text)
        for later in range(idx + 1, len(matches)):
            later_sid = resolve_section_id(
                matches[later].group(2).strip(), aliases=aliases
            )
            if later_sid in canonical:
                end = matches[later].start()
                break
        chunk = text[start:end].strip()
        if sid in seen:
            removed += 1
            continue
        seen.add(sid)
        kept_chunks.append(chunk)

    if removed == 0:
        return source, []

    parts: list[str] = []
    if preamble:
        parts.append(preamble)
    parts.extend(kept_chunks)
    return "\n\n".join(parts) + "\n", [f"removed {removed} duplicate section(s)"]


def normalize_report_deliverable(
    text: str,
    *,
    session_visual_links: list[dict[str, Any]] | None = None,
    filter_context: Any | None = None,
    inject_missing_charts: bool = True,
) -> tuple[str, list[str]]:
    """Repair charts/sections in memory before validate or write-back."""
    notes: list[str] = []
    text, n = fix_wrong_report_chart_syntax(text)
    notes.extend(n)
    text, n = normalize_report_headings(text)
    notes.extend(n)
    text, n = repair_report_chart_fences(text)
    notes.extend(n)
    text, n = sync_report_chart_week_view_params(
        text,
        session_visual_links,
        filter_context,
    )
    notes.extend(n)
    text, n = dedupe_report_sections(text)
    notes.extend(n)
    text, n = dedupe_report_chart_fences(text)
    notes.extend(n)
    if inject_missing_charts and session_visual_links:
        text, n = inject_report_charts_from_links(text, session_visual_links)
        notes.extend(n)
        text, n = dedupe_report_chart_fences(text)
        notes.extend(n)
    return text, notes


def finalize_report_markdown(
    text: str,
    *,
    path: str | Path | None = None,
    analysis_context: AnalysisToolContext | None = None,
    session_visual_links: list[dict[str, Any]] | None = None,
    filter_context: Any | None = None,
) -> dict[str, Any]:
    """Normalize then validate; does not write to disk."""
    links = session_visual_links
    if links is None and analysis_context is not None:
        links = analysis_context.session_visual_links
    normalized, notes = normalize_report_deliverable(
        text,
        session_visual_links=links,
        filter_context=filter_context,
    )
    tier = infer_tier_from_path(path) if path else None
    validation = validate_report(
        normalized,
        tier=tier,
        path=path,
        analysis_context=analysis_context,
        validation_level="deliver",
    )
    validation["normalized_text"] = normalized
    validation["fixes"] = notes
    return validation


def _load_filter_context_for_session(session_id: str | None) -> Any | None:
    if not session_id:
        return None
    from common.paths import AGENT_STATE_DIR
    from data.filter_context import FilterContext

    path = AGENT_STATE_DIR / "sessions" / session_id / "filter_context.json"
    if not path.is_file():
        return None
    try:
        import json

        return FilterContext.from_dict(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return None


def finalize_report_file(
    rel_path: str | Path,
    *,
    analysis_context: AnalysisToolContext | None = None,
    session_visual_links: list[dict[str, Any]] | None = None,
    turn_snapshots: list[QuerySnapshot] | None = None,
    session_id: str | None = None,
    filter_context: Any | None = None,
    write_back: bool = True,
) -> dict[str, Any]:
    """Last-mile check: auto-fix, optionally persist, return validation JSON."""
    from common.paths import DATA_DIR
    from permission.paths import normalize_path

    rel_norm = normalize_path(str(rel_path))
    full = (DATA_DIR / rel_norm).resolve()
    if not full.is_file():
        return {
            "ok": False,
            "path": rel_norm,
            "errors": [f"report file not found: {rel_norm}"],
            "warnings": [],
            "fixes": [],
        }

    ctx = analysis_context
    if ctx is None and turn_snapshots is not None:
        ctx = AnalysisToolContext(turn_snapshots=list(turn_snapshots))

    fc = filter_context
    if fc is None:
        sid = session_id or (ctx.session_id if ctx else None)
        fc = _load_filter_context_for_session(sid)

    original = full.read_text(encoding="utf-8")
    result = finalize_report_markdown(
        original,
        path=rel_norm,
        analysis_context=ctx,
        session_visual_links=session_visual_links,
        filter_context=fc,
    )
    normalized = result.pop("normalized_text", original)
    fixes = result.pop("fixes", [])

    if write_back and normalized != original:
        full.write_text(normalized, encoding="utf-8", newline="\n")

    return {
        "ok": bool(result.get("ok")),
        "path": rel_norm,
        "tier": result.get("tier"),
        "line_count": result.get("line_count"),
        "delivery_status": result.get("delivery_status"),
        "section_coverage": result.get("section_coverage"),
        "errors": result.get("errors") or [],
        "warnings": result.get("warnings") or [],
        "fixes": fixes,
        "summary": format_validation_for_tool_result(result),
    }

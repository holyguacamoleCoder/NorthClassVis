"""Promote ###/#### section titles to canonical ## <id> headings."""

from __future__ import annotations

from .parse import load_canonical_section_ids, parse_report_markdown


def normalize_report_headings(source: str) -> tuple[str, list[str]]:
    """
    Rewrite recognized sections as ## <canonical_id> for stable edit_file / validate.

    Leaves preamble (title lines) intact; drops unrecognized headings from section list.
    """
    parsed = parse_report_markdown(source)
    if not parsed.sections:
        return source, []

    canonical = load_canonical_section_ids()
    kept = [s for s in parsed.sections if s.id in canonical]
    if not kept:
        return source, []

    parts: list[str] = []
    if parsed.preamble.strip():
        parts.append(parsed.preamble.strip())
    for section in kept:
        parts.append(f"## {section.id}\n\n{section.body}".rstrip())
    rebuilt = "\n\n".join(parts) + "\n"

    if rebuilt.strip() == (source or "").strip():
        return source, []
    return rebuilt, ["normalized report section headings to ## <id>"]

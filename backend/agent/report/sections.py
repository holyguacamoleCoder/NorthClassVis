from __future__ import annotations

import re

from .parse import normalize_section_id as normalize_section_id

_SECTION_HEADING_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)


def _heading_matches(section_title: str, needle: str) -> bool:
    a = normalize_section_id(section_title)
    b = normalize_section_id(needle)
    if a == b:
        return True
    return section_title.strip().lower() == needle.strip().lower()


def find_section_span(content: str, section_heading: str) -> tuple[int, int] | None:
    """Return (start, end) byte offsets for a ## section body (through line before next ##)."""
    needle = section_heading.strip()
    if needle.startswith("##"):
        needle = needle[2:].strip()
    matches = list(_SECTION_HEADING_RE.finditer(content or ""))
    for idx, match in enumerate(matches):
        title = match.group(1).strip()
        if not _heading_matches(title, needle):
            continue
        start = match.start()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(content)
        return start, end
    return None


def replace_section(content: str, section_heading: str, new_section: str) -> str | None:
    """Replace entire ## section; new_section should include the ## heading line."""
    span = find_section_span(content, section_heading)
    if span is None:
        return None
    start, end = span
    replacement = new_section.rstrip() + "\n\n"
    return content[:start] + replacement + content[end:].lstrip()


def append_section(content: str, new_section: str) -> str:
    """Append a ## section before evidence/limitations, or at document end."""
    block = new_section.rstrip() + "\n\n"
    lowered = (content or "").lower()
    for marker in ("## evidence", "## limitations"):
        idx = lowered.find(marker)
        if idx >= 0:
            return content[:idx].rstrip() + "\n\n" + block + content[idx:].lstrip()
    base = (content or "").rstrip()
    return f"{base}\n\n{block}" if base else block


def section_excerpt(content: str, section_heading: str, *, body_lines: int = 14) -> str | None:
    span = find_section_span(content, section_heading)
    if span is None:
        return None
    chunk = content[span[0] : span[1]].rstrip()
    lines = chunk.splitlines()
    if len(lines) > body_lines + 1:
        chunk = "\n".join(lines[: body_lines + 1]) + "\n…"
    return chunk


def edit_context_hint(content: str, old_text: str, *, max_lines: int = 16) -> str:
    """Build a short hint when exact old_text is missing."""
    lines = [ln for ln in (old_text or "").splitlines() if ln.strip()]
    if lines and lines[0].strip().startswith("##"):
        excerpt = section_excerpt(content, lines[0].strip())
        if excerpt:
            return (
                f"[Edit hint] Section not matched exactly. Current file excerpt:\n"
                f"```\n{excerpt}\n```\n"
                "Copy a substring from the excerpt as old_text, or pass only the ## heading "
                "as the first line of old_text to replace the whole section."
            )
    snippet = (old_text or "").strip()[:80]
    if snippet:
        lowered = content.lower()
        pos = lowered.find(snippet.lower()[:40]) if len(snippet) >= 8 else -1
        if pos >= 0:
            start = max(0, content.rfind("\n", 0, pos) + 1)
            excerpt_lines = content[start:].splitlines()[:max_lines]
            excerpt = "\n".join(excerpt_lines)
            return (
                f"[Edit hint] Near match in file:\n```\n{excerpt}\n```\n"
                "Use read_file and copy old_text exactly (spaces and punctuation)."
            )
    head = "\n".join((content or "").splitlines()[:max_lines])
    return (
        f"[Edit hint] File starts with:\n```\n{head}\n```\n"
        f"| Next: read_file path=\"…\" then copy exact old_text"
    )

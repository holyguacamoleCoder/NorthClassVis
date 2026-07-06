"""Detect report edit / validate loops to stop empty churn."""

from __future__ import annotations

import re
from typing import Any

_WRITE_TOOLS = frozenset({"write_file", "edit_file"})
_ERROR_LINE_RE = re.compile(r"^\s*error:\s*(.+)$", re.MULTILINE | re.IGNORECASE)


def report_validate_blocker_signature(content: str) -> str | None:
    """Fingerprint blocking report validation (status fail / Error prefix)."""
    text = content or ""
    if "[Report validate]" not in text:
        return None
    block = text[text.find("[Report validate]") :]
    if "Error: Report validation failed" not in text and "status: fail" not in block:
        if "status: ERRORS" not in block:
            return None
    errors = _ERROR_LINE_RE.findall(block)
    if errors:
        return "blocker:" + "|".join(errors[:2])
    return "blocker:unknown"


def report_validate_soft_signature(content: str) -> str | None:
    """Fingerprint non-blocking validation (warn-only or OK)."""
    text = content or ""
    if "[Report validate: OK]" in text and "warn:" not in text:
        return "ok"
    if "status: warn" in text or "status: OK with warnings" in text:
        warns = re.findall(r"^\s*warn:\s*(.+)$", text, re.MULTILINE | re.IGNORECASE)
        return "warn:" + "|".join(warns[:2]) if warns else "warn:generic"
    if "[Report validate: OK]" in text:
        return "ok"
    return None


def collect_report_tool_signatures(
    tool_calls: list[dict[str, Any]],
    tool_results: list[dict[str, Any]],
) -> list[str]:
    by_id = {c.get("id"): c.get("name") for c in tool_calls if c.get("id")}
    out: list[str] = []
    for result in tool_results:
        name = by_id.get(result.get("tool_call_id"))
        if name not in _WRITE_TOOLS:
            continue
        content = str(result.get("content") or "")
        sig = report_validate_blocker_signature(content) or report_validate_soft_signature(content)
        if sig:
            out.append(sig)
    return out

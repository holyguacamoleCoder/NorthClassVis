"""Extract compact summaries from tool JSON for micro-compaction."""

from __future__ import annotations

import json
from typing import Any


def extract_tabular_summary(content: str) -> str | None:
    """One-line summary for query_data / aggregate_data JSON results."""
    if not content or not isinstance(content, str):
        return None
    stripped = content.strip()
    if stripped.startswith("Error:"):
        return stripped[:240]
    try:
        data = json.loads(stripped)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    return _summary_from_payload(data)


def _summary_from_payload(data: dict[str, Any]) -> str | None:
    meta = data.get("meta") or {}
    parts: list[str] = []
    resource = data.get("resource") or meta.get("resource")
    if resource:
        parts.append(f"resource={resource}")
    if meta.get("result_ref"):
        parts.append(f"result_ref={meta['result_ref']}")
    if meta.get("rows_scanned") is not None:
        parts.append(f"rows_scanned={meta['rows_scanned']}")
    if meta.get("truncated") is not None:
        parts.append(f"truncated={meta['truncated']}")
    if data.get("rows") is not None and not meta.get("result_ref"):
        parts.append(f"preview_rows={len(data['rows'])}")
    next_step = meta.get("next_step")
    if isinstance(next_step, dict) and next_step.get("tool"):
        parts.append(f"next={next_step['tool']}")
    if not parts:
        return None
    return "[Summary] " + ", ".join(parts)


def append_query_summary_to_result(tool_result: str) -> str:
    """Prepend a one-line summary before large query_data JSON (PostToolUse-style)."""
    summary = extract_tabular_summary(tool_result)
    if not summary or summary.startswith("Error:"):
        return tool_result
    if tool_result.startswith(summary):
        return tool_result
    return f"{summary}\n\n{tool_result}"

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
    label = meta.get("label")
    if label:
        parts.append(f"label={label}")
    grain = meta.get("grain")
    if grain:
        parts.append(f"grain={grain}")
    resource = data.get("resource") or meta.get("resource")
    if resource and not label:
        parts.append(f"resource={resource}")
    # Keep dataset handles so micro-compact / list_datasets continuity survives.
    dataset_id = meta.get("dataset_id") or data.get("dataset_id")
    if dataset_id:
        parts.append(f"dataset_id={dataset_id}")
    parent_id = meta.get("parent_dataset_id")
    if parent_id:
        parts.append(f"parent={parent_id}")
    result_ref = meta.get("result_ref") or data.get("result_ref")
    if result_ref:
        parts.append(f"result_ref={result_ref}")
    dims = meta.get("dimensions")
    if dims:
        parts.append(f"dimensions={','.join(str(d) for d in dims)}")
    cols = meta.get("columns")
    if cols and grain == "agg":
        parts.append(f"cols={','.join(str(c) for c in cols[:8])}")
    if meta.get("query_limit") is not None:
        parts.append(f"query_limit={meta['query_limit']}")
    if meta.get("rows_scanned") is not None:
        parts.append(f"rows_scanned={meta['rows_scanned']}")
    if meta.get("truncated") is not None:
        parts.append(f"truncated={meta['truncated']}")
        full_n = meta.get("full_row_count")
        preview_n = meta.get("preview_row_count")
        if full_n is not None:
            parts.append(f"full_rows={full_n}")
        if preview_n is not None:
            parts.append(f"preview_rows={preview_n}")
        if meta.get("truncated") and result_ref:
            parts.append("preview_only_full_in_result_ref")
            parts.append("prefer_order_by_limit_for_topk")
    if meta.get("aggregate_limit") is not None:
        parts.append(f"agg_limit={meta['aggregate_limit']}")
    if data.get("rows") is not None and not result_ref:
        parts.append(f"preview_rows={len(data['rows'])}")
    if meta.get("reused"):
        parts.append("reused=true")
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

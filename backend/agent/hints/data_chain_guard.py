"""Detect query ↔ aggregate oscillation (not just identical batch dedupe)."""

from __future__ import annotations

import json
import re
from typing import Any

from tools.runtime.pipeline.preprocess import parse_args

_AGGREGATE_TOOLS = frozenset({"aggregate_data"})
_QUERY_TOOL = "query_data"

_AGGREGATE_RETRY_MARKERS = (
    "绑定 scope=class_wide",
    "绑定 scope=chain_slice",
    "aggregate_data 需要 input",
    "input is required",
    "dataset_id",
    "RESULT_REF_CORRECTED",
)

_DS_ID_RE = re.compile(r"ds_[a-f0-9]+", re.IGNORECASE)
_REF_RE = re.compile(r"query-results/[a-f0-9]+\.json", re.IGNORECASE)
_ROW_COUNT_RE = re.compile(r"\d+\s*行")


def normalize_aggregate_error(content: str) -> str | None:
    """Stable fingerprint for repeated aggregate failures (strip volatile ids)."""
    text = (content or "").strip()
    if not text.startswith("Error:"):
        return None
    if not any(marker in text for marker in _AGGREGATE_RETRY_MARKERS):
        return None
    line = text.split("\n", 1)[0]
    line = _DS_ID_RE.sub("ds_*", line)
    line = _REF_RE.sub("query-results/*.json", line)
    line = _ROW_COUNT_RE.sub("N行", line)
    return line[:240]


def normalize_query_data_signature(call: dict[str, Any]) -> str | None:
    """Ignore select/order_by/limit — only resource + class scope + week_range."""
    if call.get("name") != _QUERY_TOOL:
        return None
    args = parse_args(call.get("arguments", {}))
    resource = args.get("resource")
    if not resource:
        return None
    classes = args.get("classes")
    if classes is None and args.get("class"):
        classes = [args.get("class")]
    payload = {
        "resource": str(resource),
        "classes": sorted(str(c) for c in classes) if classes else None,
        "week_range": args.get("week_range"),
        "majors": sorted(str(m) for m in args.get("majors") or []) or None,
    }
    return json.dumps(payload, sort_keys=True, ensure_ascii=False)


def aggregate_errors_in_batch(
    tool_calls: list[dict[str, Any]],
    tool_results: list[dict[str, Any]],
) -> list[str]:
    by_id = {c.get("id"): c.get("name") for c in tool_calls if c.get("id")}
    for result in tool_results:
        if by_id.get(result.get("tool_call_id")) not in _AGGREGATE_TOOLS:
            continue
        sig = normalize_aggregate_error(str(result.get("content") or ""))
        if sig:
            return [sig]
    return []


def query_signatures_in_batch(tool_calls: list[dict[str, Any]]) -> list[str]:
    out: list[str] = []
    for call in tool_calls:
        sig = normalize_query_data_signature(call)
        if sig:
            out.append(sig)
    return out


def should_break_aggregate_retry_loop(
    recent_signatures: list[str],
    *,
    window: int,
) -> bool:
    if len(recent_signatures) < window:
        return False
    tail = recent_signatures[-window:]
    return len(set(tail)) == 1


def should_break_repeated_query_loop(
    recent_query_signatures: list[str],
    *,
    window: int,
    repeat_threshold: int,
) -> bool:
    if len(recent_query_signatures) < repeat_threshold:
        return False
    tail = recent_query_signatures[-window:]
    if not tail:
        return False
    from collections import Counter

    counts = Counter(tail)
    _sig, n = counts.most_common(1)[0]
    return n >= repeat_threshold

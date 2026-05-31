"""Canonical column name normalization against dataset schema (no ad-hoc alias tables)."""

from __future__ import annotations

import difflib
import re
from functools import lru_cache
from typing import Any

# Resource → columns (mirrors data/meta/resource_registry.yaml; used for hints only).
RESOURCE_COLUMNS: dict[str, tuple[str, ...]] = {
    "submit_record": (
        "index",
        "class",
        "time",
        "state",
        "score",
        "title_ID",
        "method",
        "memory",
        "timeconsume",
        "student_ID",
        "knowledge",
        "sub_knowledge",
        "major",
        "sex",
        "age",
    ),
    "week_aggregation": ("student_ID", "week_index", "peak_value", "direction"),
    "student_info": ("index", "student_ID", "sex", "age", "major"),
    "title_info": ("index", "title_ID", "score", "knowledge", "sub_knowledge"),
}

FIELD_RESOURCE_HINTS: dict[str, str] = {
    "week_index": "week_aggregation（列名 week_index，勿写 week）",
    "peak_value": "week_aggregation",
    "direction": "week_aggregation",
    "score": "submit_record 或 title_info（week_aggregation 无 score）",
    "title_ID": "submit_record 或 title_info（week_aggregation 无 title_ID）",
    "knowledge": "submit_record 或 title_info",
    "major": "submit_record 或 student_info",
}


def normalize_identifier(name: str) -> str:
    """Unify casing / separators: camelCase, kebab, spaces → lowercase snake."""
    s = str(name or "").strip()
    if not s:
        return ""
    s = re.sub(r"[-\s]+", "_", s)
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s)
    s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", s)
    return s.lower()


def _lookup_keys_for_column(column: str) -> set[str]:
    keys = {column, column.lower(), normalize_identifier(column)}
    return {k for k in keys if k}


@lru_cache(maxsize=128)
def _build_column_lookup(columns_tuple: tuple[str, ...]) -> dict[str, str]:
    """Map normalized tokens → canonical column name from schema."""
    lookup: dict[str, str] = {}
    for col in columns_tuple:
        for key in _lookup_keys_for_column(col):
            lookup.setdefault(key, col)
    return lookup


def _prefix_unique_match(token: str, available: list[str]) -> str | None:
    """
    When token is a short prefix (e.g. week), pick the sole column week_* .
    Avoids hard-coding week → week_index when schema already defines week_index.
    """
    norm = normalize_identifier(token)
    if not norm or len(norm) < 2:
        return None
    candidates = [
        col
        for col in available
        if normalize_identifier(col) == norm
        or normalize_identifier(col).startswith(f"{norm}_")
    ]
    if len(candidates) == 1:
        return candidates[0]
    return None


def resolve_column(name: str, available: list[str]) -> str | None:
    """Match input to a schema column via normalization, then prefix/fuzzy."""
    if not name or not available:
        return None
    if name in available:
        return name

    lookup = _build_column_lookup(tuple(available))
    for key in _lookup_keys_for_column(name):
        if key in lookup:
            return lookup[key]

    prefix = _prefix_unique_match(name, available)
    if prefix:
        return prefix

    norm_name = normalize_identifier(name)
    norm_available = {normalize_identifier(c): c for c in available}
    if norm_name in norm_available:
        return norm_available[norm_name]

    fuzzy_pool = list(norm_available.keys())
    matches = difflib.get_close_matches(norm_name, fuzzy_pool, n=1, cutoff=0.85)
    if matches:
        return norm_available[matches[0]]

    return None


def resolve_columns(
    names: list[str],
    available: list[str],
) -> tuple[list[str], list[str], list[str]]:
    """Returns (resolved, unresolved, repair_notes)."""
    resolved: list[str] = []
    unresolved: list[str] = []
    notes: list[str] = []
    for name in names:
        fixed = resolve_column(name, available)
        if fixed:
            if fixed != name:
                notes.append(f"列名 {name!r} 已规范为 {fixed!r}")
            resolved.append(fixed)
        else:
            unresolved.append(name)
    return resolved, unresolved, notes


def resolve_metrics_columns(
    metrics: list[dict[str, Any]],
    available: list[str],
) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    out: list[dict[str, Any]] = []
    unresolved: list[str] = []
    notes: list[str] = []
    for metric in metrics:
        m = dict(metric)
        field = m.get("field")
        if field:
            fixed = resolve_column(str(field), available)
            if fixed:
                if fixed != field:
                    notes.append(f"metric.field {field!r} 已规范为 {fixed!r}")
                m["field"] = fixed
            else:
                unresolved.append(str(field))
        out.append(m)
    return out, unresolved, notes


def format_missing_columns_error(
    *,
    param: str,
    missing: list[str],
    available: list[str],
    resource: str | None = None,
    repair_notes: list[str] | None = None,
) -> str:
    parts = [f"{param} 列/字段不存在: {missing}"]
    if repair_notes:
        parts.append("已尝试规范化: " + "; ".join(repair_notes))
    if available:
        preview = available[:20]
        suffix = "…" if len(available) > 20 else ""
        parts.append(f"当前数据集可用列: {preview}{suffix}")
    hints: list[str] = []
    for col in missing:
        hint = FIELD_RESOURCE_HINTS.get(col)
        if hint:
            hints.append(f"{col} → {hint}")
            continue
        suggestion = resolve_column(col, available)
        if suggestion and suggestion != col:
            hints.append(f"{col} → 请改用 {suggestion!r}")
        elif available:
            close = difflib.get_close_matches(
                normalize_identifier(col),
                [normalize_identifier(c) for c in available],
                n=1,
                cutoff=0.6,
            )
            if close:
                idx = [normalize_identifier(c) for c in available].index(close[0])
                hints.append(f"{col} → 近似列 {available[idx]!r}")
    if resource and resource in RESOURCE_COLUMNS:
        hints.append(f"{resource} 标准列: {list(RESOURCE_COLUMNS[resource])}")
    if hints:
        parts.append("提示: " + "; ".join(hints))
    return " | ".join(parts)

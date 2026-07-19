"""Human-readable dataset identity (grain / label) to avoid ambiguous 指代."""

from __future__ import annotations

from typing import Any


GRAIN_ROW = "row"
GRAIN_AGG = "agg"


def column_names_from_payload(payload: dict[str, Any] | None) -> list[str]:
    """Extract column names from tabular payload (schema / columns / dict rows)."""
    if not isinstance(payload, dict):
        return []
    names: list[str] = []
    # Canonical tabular shape from query/aggregate: schema=[{name, type}, ...]
    for col in payload.get("schema") or []:
        if isinstance(col, dict) and col.get("name"):
            names.append(str(col["name"]))
        elif isinstance(col, str) and col.strip():
            names.append(col.strip())
    if names:
        return names
    for col in payload.get("columns") or []:
        if isinstance(col, dict) and col.get("name"):
            names.append(str(col["name"]))
        elif isinstance(col, str) and col.strip():
            names.append(col.strip())
    if names:
        return names
    meta = payload.get("meta") or {}
    for col in meta.get("columns") or []:
        if isinstance(col, dict) and col.get("name"):
            names.append(str(col["name"]))
        elif isinstance(col, str) and col.strip():
            names.append(col.strip())
    if names:
        return names
    rows = payload.get("rows")
    if isinstance(rows, list) and rows and isinstance(rows[0], dict):
        return [str(k) for k in rows[0].keys()]
    return []


def infer_grain(
    *,
    tool_name: str | None = None,
    parsed_args: dict[str, Any] | None = None,
    payload: dict[str, Any] | None = None,
) -> str:
    if tool_name == "aggregate_data":
        return GRAIN_AGG
    args = parsed_args or {}
    if args.get("dimensions") is not None or args.get("metrics") is not None:
        return GRAIN_AGG
    meta = (payload or {}).get("meta") or {}
    if meta.get("grain") in (GRAIN_ROW, GRAIN_AGG):
        return str(meta["grain"])
    if meta.get("aggregate") or meta.get("dimensions"):
        return GRAIN_AGG
    return GRAIN_ROW


def _week_span_from_where(where: Any) -> str | None:
    if not isinstance(where, dict):
        return None
    lo = hi = None
    leaves: list[dict] = []
    if where.get("op") == "and":
        for cond in where.get("conditions") or []:
            if isinstance(cond, dict):
                leaves.append(cond)
    else:
        leaves.append(where)
    for leaf in leaves:
        field = str(leaf.get("field") or "")
        if field not in ("week_index", "week"):
            continue
        op = leaf.get("op")
        val = leaf.get("value")
        try:
            n = int(val) if val is not None else None
        except (TypeError, ValueError):
            n = None
        if n is None:
            continue
        if op in ("gte", "gt", "eq"):
            lo = n if lo is None else min(lo, n)
            if op == "eq":
                hi = n if hi is None else max(hi, n)
        if op in ("lte", "lt", "eq"):
            hi = n if hi is None else max(hi, n)
            if op == "eq":
                lo = n if lo is None else min(lo, n)
        if op == "between" and isinstance(val, (list, tuple)) and len(val) == 2:
            try:
                a, b = int(val[0]), int(val[1])
                lo, hi = min(a, b), max(a, b)
            except (TypeError, ValueError):
                pass
    if lo is None and hi is None:
        return None
    if lo is not None and hi is not None:
        return f"周{lo}-{hi}" if lo != hi else f"周{lo}"
    if lo is not None:
        return f"周≥{lo}"
    return f"周≤{hi}"


def _class_label(classes: list[str] | None, parsed_args: dict[str, Any] | None) -> str | None:
    if classes:
        return "+".join(str(c) for c in classes[:4])
    args = parsed_args or {}
    c = args.get("class") or args.get("classes")
    if isinstance(c, list) and c:
        return "+".join(str(x) for x in c[:4])
    if c:
        return str(c)
    return None


def build_dataset_label(
    *,
    grain: str,
    resource: str | None,
    classes: list[str] | None = None,
    parsed_args: dict[str, Any] | None = None,
    columns: list[str] | None = None,
    dimensions: list[str] | None = None,
    result_rows: int | None = None,
    query_limit: int | None = None,
) -> str:
    """Short teacher/agent-facing tag, e.g. Class2·周13-15·submit_record·原始行."""
    parts: list[str] = []
    cls = _class_label(classes, parsed_args)
    if cls:
        parts.append(cls)
    where = (parsed_args or {}).get("where") or (parsed_args or {}).get("filter")
    week = _week_span_from_where(where)
    if week:
        parts.append(week)
    if resource:
        parts.append(str(resource))
    if grain == GRAIN_AGG:
        dims = dimensions or []
        if dims:
            parts.append("按" + "+".join(str(d) for d in dims[:4]) + "汇总")
        else:
            parts.append("聚合表")
        # Explicit warning when student grain is missing
        cols = set(columns or [])
        if "student_ID" not in cols and "student_id" not in cols:
            parts.append("无学号列")
    else:
        parts.append("原始行")
        if query_limit is not None:
            parts.append(f"limit={query_limit}")
        else:
            parts.append("全量")
    if result_rows is not None:
        parts.append(f"{result_rows}行")
    return "·".join(parts) if parts else ("聚合表" if grain == GRAIN_AGG else "原始行")


def describe_for_catalog(rec_like: dict[str, Any]) -> str:
    """One-line identity for prompts / list_datasets."""
    label = rec_like.get("label") or ""
    grain = rec_like.get("grain") or "?"
    ds = rec_like.get("dataset_id") or "?"
    cols = rec_like.get("columns") or rec_like.get("select_cols") or []
    col_preview = ",".join(str(c) for c in cols[:6])
    if len(cols) > 6:
        col_preview += "…"
    bits = [f"{ds}", f"grain={grain}"]
    if label:
        bits.append(label)
    if col_preview:
        bits.append(f"cols=[{col_preview}]")
    parent = rec_like.get("parent_dataset_id")
    if parent:
        bits.append(f"parent={parent}")
    return " | ".join(bits)

"""Resolve-parameter validation and normalization for logical resources."""

from __future__ import annotations

import re
from typing import Any

from .exceptions import InvalidParameterError

_SUBMIT_RECORD = "submit_record"
_WEEK_AGGREGATION = "week_aggregation"
_DEPRECATED_SUBMIT_JOINED = "submit_record_joined"
_MAJOR_CODE_RE = re.compile(r"^J\d+$")
_WEEK_FIELD_TOKENS = frozenset({"week", "week_index"})


def _iter_where_leaves(where: dict | None) -> list[dict]:
    if not where or not isinstance(where, dict):
        return []
    if where.get("op") == "and":
        leaves: list[dict] = []
        for cond in where.get("conditions") or []:
            if isinstance(cond, dict):
                leaves.extend(_iter_where_leaves(cond))
        return leaves
    return [where]


def _looks_like_major_code(value: Any) -> bool:
    return isinstance(value, str) and bool(_MAJOR_CODE_RE.match(value))


def validate_submit_where(where: dict | None) -> None:
    """Reject common mistake: filtering student_ID with a major code like J23517."""
    for leaf in _iter_where_leaves(where):
        if leaf.get("field") != "student_ID":
            continue
        op = leaf.get("op")
        value = leaf.get("value")
        candidates: list[Any] = []
        if op == "eq":
            candidates = [value]
        elif op == "in" and isinstance(value, list):
            candidates = value
        for candidate in candidates:
            if _looks_like_major_code(candidate):
                raise InvalidParameterError(
                    f"{candidate!r} 是专业代码（major），不是 student_ID。"
                    "请使用 majors=['...'] 或 where={{\"field\":\"major\",\"op\":\"eq\",\"value\":\"...\"}}。",
                    param="where",
                )


def validate_resolve_params(resource_id: str, params: dict[str, Any]) -> None:
    """Reject parameter combinations that are silently ignored by loaders."""
    majors = params.get("majors")
    if not majors:
        return
    if resource_id in ("student_info", "title_info"):
        raise InvalidParameterError(
            f"{resource_id} 不支持 majors；请在 submit_record 上过滤专业。",
            param="majors",
        )


def _ensure_classes(out: dict[str, Any], notes: list[str]) -> None:
    if not out.get("classes") and out.get("class"):
        out["classes"] = [out.pop("class")]
        notes.append("已将 class 转为 classes 数组。")


def _week_field_token(field: str) -> str:
    from .column_aliases import normalize_identifier

    return normalize_identifier(field)


def _uses_week_dimension(
    *,
    group_by: list[str] | None,
    order_by: list[dict[str, str]] | None,
) -> bool:
    if group_by:
        for name in group_by:
            if _week_field_token(str(name)) in _WEEK_FIELD_TOKENS:
                return True
    if order_by:
        for item in order_by:
            if not isinstance(item, dict):
                continue
            field = item.get("field")
            if field and _week_field_token(str(field)) in _WEEK_FIELD_TOKENS:
                return True
    return False


def _is_week_where_leaf(where: dict[str, Any]) -> bool:
    field = where.get("field")
    return isinstance(field, str) and _week_field_token(field) in _WEEK_FIELD_TOKENS


def _extract_week_range_from_where(
    where: dict[str, Any] | None,
) -> tuple[list[int] | None, dict[str, Any] | None, list[str]]:
    """Pull week_index/week bounds into week_range; drop those leaves from where."""
    if not where or not isinstance(where, dict):
        return None, where, []

    op = where.get("op")
    if op == "and":
        notes: list[str] = []
        kept: list[dict[str, Any]] = []
        lows: list[int] = []
        highs: list[int] = []
        eqs: list[int] = []
        for cond in where.get("conditions") or []:
            if not isinstance(cond, dict):
                kept.append(cond)
                continue
            if _is_week_where_leaf(cond):
                value = cond.get("value")
                op_leaf = cond.get("op")
                if op_leaf == "gte" and value is not None:
                    lows.append(int(value))
                elif op_leaf == "lte" and value is not None:
                    highs.append(int(value))
                elif op_leaf == "eq" and value is not None:
                    eqs.append(int(value))
                continue
            wr, cleaned, sub_notes = _extract_week_range_from_where(cond)
            notes.extend(sub_notes)
            if wr is not None:
                lows.append(int(wr[0]))
                highs.append(int(wr[1]))
            if cleaned is not None:
                kept.append(cleaned)
        week_range: list[int] | None = None
        if lows and highs:
            week_range = [min(lows), max(highs)]
        elif lows:
            week_range = [min(lows), max(lows)]
        elif highs:
            week_range = [min(highs), max(highs)]
        elif eqs:
            week_range = [min(eqs), max(eqs)]
        if week_range is not None:
            notes.append(f"已将 where 中的周次条件转为 week_range={week_range}。")
        if not kept:
            return week_range, None, notes
        if len(kept) == 1:
            return week_range, kept[0], notes
        return week_range, {"op": "and", "conditions": kept}, notes

    if _is_week_where_leaf(where):
        value = where.get("value")
        op_leaf = where.get("op")
        if op_leaf == "eq" and value is not None:
            v = int(value)
            return [v, v], None, [f"已将 where 中的周次条件转为 week_range={[v, v]}。"]
        return None, None, []

    return None, where, []


def repair_submit_record_week_usage(
    resource: str,
    kwargs: dict[str, Any],
    *,
    where: dict[str, Any] | None = None,
    group_by: list[str] | None = None,
    order_by: list[dict[str, str]] | None = None,
) -> tuple[
    str,
    dict[str, Any],
    dict[str, Any] | None,
    list[str] | None,
    list[dict[str, str]] | None,
    list[str],
]:
    """
    Auto-switch submit_record + week dimension → week_aggregation.
    week_index in group_by/order_by is valid on week_aggregation rows.
    """
    if resource != _SUBMIT_RECORD:
        return resource, kwargs, where, group_by, order_by, []
    from .column_aliases import RESOURCE_COLUMNS

    if "week_index" in RESOURCE_COLUMNS.get(_SUBMIT_RECORD, ()):
        return resource, kwargs, where, group_by, order_by, []
    if not _uses_week_dimension(group_by=group_by, order_by=order_by):
        return resource, kwargs, where, group_by, order_by, []

    notes = [
        "submit_record 无 week/week_index 列；已自动改用 resource=week_aggregation。"
        "按周趋势请优先 week_aggregation + week_range，勿对 submit_record 使用 week_index。"
    ]
    out = dict(kwargs)
    _ensure_classes(out, notes)

    week_range, cleaned_where, wr_notes = _extract_week_range_from_where(where)
    notes.extend(wr_notes)
    if week_range is not None and not out.get("week_range"):
        out["week_range"] = week_range

    return _WEEK_AGGREGATION, out, cleaned_where, group_by, order_by, notes


def normalize_query_resource(
    resource: str,
    kwargs: dict[str, Any],
    *,
    where: dict | None = None,
) -> tuple[str, dict[str, Any], list[str]]:
    """
    Auto-correct common mistakes. Returns (resource, kwargs_copy, notes for the model).
    """
    notes: list[str] = []
    out = dict(kwargs)

    if resource == _DEPRECATED_SUBMIT_JOINED:
        resource = _SUBMIT_RECORD
        notes.append(
            "submit_record_joined 已合并为 submit_record；请今后只使用 submit_record。"
        )

    if resource == _SUBMIT_RECORD:
        _ensure_classes(out, notes)
        validate_submit_where(where)

    if resource in ("student_info", "title_info"):
        if out.get("classes") or out.get("class"):
            notes.append(
                f"{resource} 无 class 列，classes/class 不会按班过滤。"
                "按班统计请用 submit_record（classes + count_distinct student_ID）或先筛 Class 学生。"
            )

    return resource, out, notes

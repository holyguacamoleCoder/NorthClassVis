"""Resolve-parameter validation and normalization for logical resources."""

from __future__ import annotations

import re
from typing import Any

from .exceptions import InvalidParameterError

_SUBMIT_RECORD = "submit_record"
_DEPRECATED_SUBMIT_JOINED = "submit_record_joined"
_MAJOR_CODE_RE = re.compile(r"^J\d+$")


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

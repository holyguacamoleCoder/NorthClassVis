from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from .exceptions import InvalidParameterError
from .result_hints import normalize_limit
from .filter_context import FilterContext, nav_scope_suppressed_reason
from .limits import QueryLimits
from .registry import default_limits, resolve
from .result_store import save_result
from .tabular import dataframe_to_tabular, validate_tabular_result
from .where import apply_where

PREVIEW_ROW_LIMIT = 50


def _apply_ui_student_selection(
    df: pd.DataFrame,
    filter_context: FilterContext | None,
    *,
    scope_suppressed: bool = False,
) -> tuple[pd.DataFrame, int | None, str | None]:
    """When the scatter plot has a selection, restrict rows to those student_IDs."""
    if scope_suppressed or filter_context is None or not filter_context.selected_student_ids:
        return df, None, None
    if "student_ID" not in df.columns:
        return df, None, None
    ids = set(filter_context.selected_student_ids)
    filtered = df[df["student_ID"].isin(ids)].copy()
    if filtered.empty and len(df) > 0:
        return (
            df,
            None,
            "面板选中学生与本次查询无交集，已忽略面板选区并按查询范围全文分析",
        )
    return filtered, len(ids), None


@dataclass
class QuerySpec:
    resource: str
    select: list[str] | None = None
    where: dict[str, Any] | None = None
    group_by: list[str] | None = None
    order_by: list[dict[str, str]] | None = None
    limit: int | None = None
    resolve_params: dict[str, Any] = field(default_factory=dict)


def _allowed_columns(resolved) -> list[str]:
    cols = resolved.schema_columns
    if cols:
        return list(cols)
    return []


def _apply_select(df: pd.DataFrame, select: list[str] | None) -> pd.DataFrame:
    if not select:
        return df
    missing = [c for c in select if c not in df.columns]
    if missing:
        raise InvalidParameterError(f"select 列不存在: {missing}", param="select")
    return df[list(select)]


def _apply_group_by(df: pd.DataFrame, group_by: list[str] | None) -> pd.DataFrame:
    if not group_by:
        return df
    missing = [c for c in group_by if c not in df.columns]
    if missing:
        raise InvalidParameterError(f"group_by 列不存在: {missing}", param="group_by")
    grouped = df.groupby(group_by, dropna=False).size().reset_index(name="count")
    return grouped


def _apply_order_by(df: pd.DataFrame, order_by: list[dict[str, str]] | None) -> pd.DataFrame:
    if not order_by:
        return df
    by: list[str] = []
    ascending: list[bool] = []
    for item in order_by:
        col = item.get("field")
        if not col or col not in df.columns:
            raise InvalidParameterError(f"order_by 列不存在: {col!r}", param="order_by")
        direction = (item.get("dir") or "asc").lower()
        by.append(col)
        ascending.append(direction != "desc")
    return df.sort_values(by=by, ascending=ascending, kind="mergesort")


def _build_tabular_from_df(
    df: pd.DataFrame,
    resource: str,
    *,
    rows_scanned: int,
    limits: QueryLimits,
    preview_limit: int = PREVIEW_ROW_LIMIT,
) -> dict:
    full = dataframe_to_tabular(
        df,
        resource,
        limits=QueryLimits(
            max_rows=len(df) if len(df) > 0 else limits.max_rows,
            max_bytes=limits.max_bytes,
            timeout_sec=limits.timeout_sec,
        ),
    )
    full["meta"]["rows_scanned"] = rows_scanned

    result_ref: str | None = None
    if len(full["rows"]) > 0:
        result_ref = save_result(full)
        full["meta"]["result_ref"] = result_ref

    if len(full["rows"]) <= preview_limit:
        full["meta"]["truncated"] = False
        return full

    preview_df = df.iloc[:preview_limit].copy()
    preview = dataframe_to_tabular(
        preview_df,
        resource,
        limits=QueryLimits(max_rows=preview_limit, max_bytes=limits.max_bytes),
    )
    preview["meta"]["rows_scanned"] = rows_scanned
    preview["meta"]["truncated"] = True
    if result_ref:
        preview["meta"]["result_ref"] = result_ref
    return preview


def execute_query(
    spec: QuerySpec,
    *,
    filter_context: FilterContext | None = None,
    teacher_message: str | None = None,
    limits: QueryLimits | None = None,
    data_dir=None,
    preview_limit: int = PREVIEW_ROW_LIMIT,
) -> dict:
    """执行查询，返回 TabularResult dict。"""
    limits = limits or default_limits()
    params = dict(spec.resolve_params)
    scope_suppressed = False
    scope_note: str | None = None
    if filter_context is not None:
        scope_note = nav_scope_suppressed_reason(
            filter_context,
            params,
            teacher_message=teacher_message,
            data_dir=data_dir,
        )
        scope_suppressed = scope_note is not None
        nav_scoped, _ = filter_context.effective_nav_scope_for_query(
            params,
            teacher_message=teacher_message,
            resource_id=spec.resource,
            data_dir=data_dir,
        )
        for key, value in nav_scoped.items():
            if key not in params or params[key] is None:
                params[key] = value

    resolved = resolve(spec.resource, data_dir=data_dir, **params)
    df = resolved.load()
    if not isinstance(df, pd.DataFrame):
        raise InvalidParameterError("loader 未返回 DataFrame", param="resource")

    df, ui_selection_count, stale_selection_note = _apply_ui_student_selection(
        df,
        filter_context,
        scope_suppressed=scope_suppressed,
    )

    allowed = _allowed_columns(resolved)
    if not allowed:
        allowed = list(df.columns)

    rows_scanned = len(df)
    working, where_notes = apply_where(df, spec.where, allowed, resource=spec.resource)
    rows_scanned = len(working)

    if spec.group_by:
        working = _apply_group_by(working, spec.group_by)
    else:
        working = _apply_select(working, spec.select)

    working = _apply_order_by(working, spec.order_by)

    if spec.limit is not None:
        effective_limit, _ = normalize_limit(spec.limit)
        if effective_limit is not None:
            if effective_limit < 0:
                raise InvalidParameterError("limit 须 >= 0", param="limit")
            working = working.head(int(effective_limit))
            if len(working) > limits.max_rows:
                working = working.iloc[: limits.max_rows].copy()
    # omit limit: keep full matching set in result_ref (preview may still truncate)

    result = _build_tabular_from_df(
        working,
        spec.resource,
        rows_scanned=rows_scanned,
        limits=limits,
        preview_limit=preview_limit,
    )
    if spec.limit is not None:
        result.setdefault("meta", {})["query_limit"] = int(spec.limit)
    if ui_selection_count is not None:
        result.setdefault("meta", {})["ui_selected_students"] = ui_selection_count
    if where_notes:
        meta = result.setdefault("meta", {})
        existing = list(meta.get("normalization_notes") or [])
        meta["normalization_notes"] = existing + where_notes
    if scope_note:
        meta = result.setdefault("meta", {})
        existing = list(meta.get("normalization_notes") or [])
        meta["normalization_notes"] = existing + [scope_note]
        meta["nav_scope_suppressed"] = True
    elif stale_selection_note:
        meta = result.setdefault("meta", {})
        existing = list(meta.get("normalization_notes") or [])
        meta["normalization_notes"] = existing + [stale_selection_note]
        meta["nav_scope_suppressed"] = True
    validate_tabular_result(result)
    return result

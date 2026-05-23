from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from .exceptions import InvalidParameterError
from .result_hints import reject_limit_zero
from .filter_context import FilterContext
from .limits import QueryLimits
from .registry import default_limits, resolve
from .result_store import save_result
from .tabular import dataframe_to_tabular, validate_tabular_result
from .where import apply_where

PREVIEW_ROW_LIMIT = 50


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
    limits: QueryLimits | None = None,
    data_dir=None,
    preview_limit: int = PREVIEW_ROW_LIMIT,
) -> dict:
    """执行查询，返回 TabularResult dict。"""
    limits = limits or default_limits()
    params = dict(spec.resolve_params)
    if filter_context is not None:
        params.update(filter_context.to_resolve_params())

    resolved = resolve(spec.resource, data_dir=data_dir, **params)
    df = resolved.load()
    if not isinstance(df, pd.DataFrame):
        raise InvalidParameterError("loader 未返回 DataFrame", param="resource")

    allowed = _allowed_columns(resolved)
    if not allowed:
        allowed = list(df.columns)

    rows_scanned = len(df)
    working = apply_where(df, spec.where, allowed)
    rows_scanned = len(working)

    if spec.group_by:
        working = _apply_group_by(working, spec.group_by)
    else:
        working = _apply_select(working, spec.select)

    working = _apply_order_by(working, spec.order_by)

    if spec.limit is not None:
        reject_limit_zero(spec.limit)
        if spec.limit < 0:
            raise InvalidParameterError("limit 须 >= 0", param="limit")
        working = working.head(int(spec.limit))
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
    validate_tabular_result(result)
    return result

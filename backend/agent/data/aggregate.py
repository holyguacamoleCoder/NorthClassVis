from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from .column_aliases import (
    format_missing_columns_error,
    resolve_columns,
    resolve_metrics_columns,
)
from .exceptions import InvalidParameterError
from .limits import QueryLimits
from .registry import default_limits
from .result_store import load_result
from .tabular import dataframe_to_tabular, validate_tabular_result
from .query import PREVIEW_ROW_LIMIT, _apply_order_by, _build_tabular_from_df

_ALLOWED_METRICS = frozenset({"count", "count_distinct", "sum", "mean", "min", "max"})


@dataclass
class AggregateSpec:
    input: dict[str, Any]
    metrics: list[dict[str, str]]
    dimensions: list[str] | None = None
    window: dict[str, Any] | None = None
    resource: str | None = None
    order_by: list[dict[str, str]] | None = None
    limit: int | None = None


def _tabular_to_dataframe(payload: dict) -> tuple[pd.DataFrame, str]:
    schema = payload.get("schema") or []
    rows = payload.get("rows") or []
    meta = payload.get("meta") or {}
    resource = meta.get("resource") or "inline"
    columns = [col["name"] for col in schema]
    df = pd.DataFrame(rows, columns=columns) if rows else pd.DataFrame(columns=columns)
    return df, resource


def _load_input_df(spec: AggregateSpec) -> tuple[pd.DataFrame, str]:
    inp = spec.input or {}
    if "result_ref" in inp:
        payload = load_result(str(inp["result_ref"]))
        return _tabular_to_dataframe(payload)
    if "rows" in inp and "schema" in inp:
        payload = {"schema": inp["schema"], "rows": inp["rows"], "meta": {"resource": spec.resource or "inline"}}
        return _tabular_to_dataframe(payload)
    raise InvalidParameterError(
        "input 须包含 result_ref 或 inline rows+schema",
        param="input",
    )


def execute_aggregate(
    spec: AggregateSpec,
    *,
    limits: QueryLimits | None = None,
    preview_limit: int = PREVIEW_ROW_LIMIT,
) -> dict:
    limits = limits or default_limits()
    df, resource = _load_input_df(spec)
    available = list(df.columns)
    repair_notes: list[str] = []

    metrics = list(spec.metrics)
    dimensions = list(spec.dimensions or [])
    if dimensions:
        dimensions, missing_dims, dim_notes = resolve_columns(dimensions, available)
        repair_notes.extend(dim_notes)
        if missing_dims:
            raise InvalidParameterError(
                format_missing_columns_error(
                    param="dimensions",
                    missing=missing_dims,
                    available=available,
                    resource=resource,
                    repair_notes=repair_notes or None,
                ),
                param="dimensions",
            )
    metrics, missing_metrics, metric_notes = resolve_metrics_columns(metrics, available)
    repair_notes.extend(metric_notes)
    if missing_metrics:
        raise InvalidParameterError(
            format_missing_columns_error(
                param="metrics",
                missing=missing_metrics,
                available=available,
                resource=resource,
                repair_notes=repair_notes or None,
            ),
            param="metrics",
        )
    spec = AggregateSpec(
        input=spec.input,
        metrics=metrics,
        dimensions=dimensions or None,
        window=spec.window,
        resource=spec.resource or resource,
        order_by=spec.order_by,
        limit=spec.limit,
    )

    if spec.window:
        field = spec.window.get("field")
        size = spec.window.get("size")
        if not field or size is None:
            raise InvalidParameterError("window 需要 field 与 size", param="window")
        if field not in df.columns:
            raise InvalidParameterError(f"window.field 不存在: {field!r}", param="window")
        df = df.sort_values(field)
        for metric in spec.metrics:
            name = metric.get("as") or f"{metric.get('op')}_{metric.get('field', field)}"
            op = metric.get("op")
            col = metric.get("field", field)
            if op not in _ALLOWED_METRICS:
                raise InvalidParameterError(f"不支持的 metric op: {op!r}", param="metrics")
            rolled = getattr(df[col].rolling(int(size), min_periods=1), op)()
            df[name] = rolled

    group_cols = list(spec.dimensions or [])

    agg_map: dict[str, list[str]] = {}
    rename: dict[tuple[str, str], str] = {}
    distinct_metrics: list[tuple[str, str]] = []
    for metric in spec.metrics:
        op = metric.get("op")
        col = metric.get("field")
        alias = metric.get("as") or (f"{op}_{col}" if col else op)
        if op not in _ALLOWED_METRICS:
            raise InvalidParameterError(f"不支持的 metric op: {op!r}", param="metrics")
        if op == "count_distinct":
            if not col or col not in df.columns:
                raise InvalidParameterError(
                    f"count_distinct 需要 field: {col!r}",
                    param="metrics",
                )
            distinct_metrics.append((col, alias))
            continue
        if op == "count" and not col:
            col = df.columns[0] if len(df.columns) else "_row"
            if col not in df.columns:
                df[col] = 1
        if not col or col not in df.columns:
            raise InvalidParameterError(f"metric 字段不存在: {col!r}", param="metrics")
        agg_map.setdefault(col, [])
        if op not in agg_map[col]:
            agg_map[col].append(op)
        rename[(col, op)] = alias

    if spec.window and not spec.metrics:
        result_df = df
    elif group_cols:
        grouped = df.groupby(group_cols, dropna=False)
        parts = []
        for col, ops in agg_map.items():
            part = grouped[col].agg(ops)
            if isinstance(part, pd.DataFrame):
                part.columns = [rename.get((col, op), f"{op}_{col}") for op in ops]
            else:
                op = ops[0]
                part = part.rename(rename.get((col, op), f"{op}_{col}"))
            parts.append(part)
        for col, alias in distinct_metrics:
            parts.append(grouped[col].nunique().rename(alias))
        result_df = pd.concat(parts, axis=1).reset_index()
    else:
        row: dict[str, Any] = {}
        for metric in spec.metrics:
            op = metric.get("op")
            col = metric.get("field")
            alias = metric.get("as") or f"{op}_{col}"
            if op == "count" and not col:
                row[alias] = len(df)
            elif op == "count_distinct":
                if not col or col not in df.columns:
                    raise InvalidParameterError(f"metric 字段不存在: {col!r}", param="metrics")
                row[alias] = int(df[col].nunique())
            else:
                if not col or col not in df.columns:
                    raise InvalidParameterError(f"metric 字段不存在: {col!r}", param="metrics")
                row[alias] = getattr(df[col], op)()
        result_df = pd.DataFrame([row])

    resource_id = spec.resource or resource
    # Optional rank/TopK on the aggregated table (keeps LLM preview small).
    result_df = _apply_order_by(result_df, spec.order_by)
    limited = False
    if spec.limit is not None:
        try:
            lim = int(spec.limit)
        except (TypeError, ValueError):
            lim = None
        if lim is not None and lim > 0:
            result_df = result_df.head(lim)
            limited = True

    n_out = len(result_df)
    result = _build_tabular_from_df(
        result_df,
        resource_id,
        rows_scanned=len(df),
        limits=limits,
        preview_limit=preview_limit,
    )
    meta = result.setdefault("meta", {})
    meta["full_row_count"] = n_out
    meta["preview_row_count"] = len(result.get("rows") or [])
    if limited:
        meta["aggregate_limit"] = int(spec.limit)  # type: ignore[arg-type]
    if spec.order_by:
        meta["aggregate_order_by"] = spec.order_by
    if meta.get("truncated"):
        meta["truncation_kind"] = "preview_only"
        meta["next_actions"] = [
            {
                "action": "rank_topk",
                "tool": "aggregate_data",
                "note": (
                    f"全量聚合共 {n_out} 行在 result_ref；预览仅 "
                    f"{meta['preview_row_count']} 行属工具预算，不是数据缺失。"
                    "要最低/最高 K 人：对同一 input.dataset_id 再调 aggregate_data，"
                    "加 order_by（按均值等指标）+ limit=K。"
                ),
            },
            {
                "action": "keep_ref",
                "note": "勿为预览截断再次 query_data 全表；换方法而不是重扫。",
            },
        ]
    elif limited:
        meta["next_actions"] = [
            {
                "action": "done_or_widen",
                "note": (
                    f"已按 order_by 取前 {n_out} 行（limit）。"
                    "若还要更多，增大 limit；若要全班表，省略 limit（仍可能预览截断，全量在 result_ref）。"
                ),
            }
        ]
    validate_tabular_result(result)
    return result

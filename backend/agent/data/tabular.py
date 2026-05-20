from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from .limits import QueryLimits, apply_column_whitelist, apply_row_limit

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_SCHEMA_PATH = _PROJECT_ROOT / "backend" / "agent" / "contracts" / "tabular_result.schema.json"

_PANDAS_TYPE_MAP = {
    "object": "string",
    "string": "string",
    "int64": "integer",
    "Int64": "integer",
    "int32": "integer",
    "float64": "number",
    "float32": "number",
    "bool": "boolean",
    "boolean": "boolean",
    "datetime64[ns]": "timestamp",
}


def _infer_column_type(dtype) -> str:
    name = str(dtype)
    for key, mapped in _PANDAS_TYPE_MAP.items():
        if key in name:
            return mapped
    return "string"


def _cell_value(value: Any) -> Any:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if hasattr(value, "item"):
        try:
            return value.item()
        except (ValueError, AttributeError):
            pass
    if isinstance(value, (pd.Int64Dtype,)):
        return value
    return value


def dataframe_to_tabular(
    df: pd.DataFrame,
    resource: str,
    *,
    limits: QueryLimits | None = None,
    meta_hints: dict | None = None,
) -> dict:
    """将 DataFrame 转为符合 tabular_result.schema.json 的 dict。"""
    meta_hints = dict(meta_hints or {})
    limits = limits or QueryLimits()

    working = apply_column_whitelist(df, limits.column_whitelist)
    limited_df, truncated, rows_scanned = apply_row_limit(working, limits)

    schema = [
        {
            "name": str(col),
            "type": _infer_column_type(limited_df[col].dtype),
        }
        for col in limited_df.columns
    ]
    rows = [
        [_cell_value(row[col]) for col in limited_df.columns]
        for _, row in limited_df.iterrows()
    ]

    meta = {"resource": resource, "truncated": truncated, "rows_scanned": rows_scanned}
    meta.update({k: v for k, v in meta_hints.items() if k not in ("resource",)})
    return {"schema": schema, "rows": rows, "meta": meta}


def validate_tabular_result(payload: dict) -> None:
    """可选：用 jsonschema 校验 TabularResult。"""
    try:
        import jsonschema
    except ImportError:
        return

    schema = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    jsonschema.validate(instance=payload, schema=schema)

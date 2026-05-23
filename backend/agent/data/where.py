from __future__ import annotations

from typing import Any

import pandas as pd

from .exceptions import InvalidParameterError

_ALLOWED_OPS = frozenset({"eq", "in", "gte", "lte", "and"})


def _validate_field(field: str, allowed_columns: frozenset[str]) -> None:
    if field not in allowed_columns:
        raise InvalidParameterError(
            f"where 字段 {field!r} 不在 resource 白名单内",
            param="where",
        )


def _apply_condition(df: pd.DataFrame, condition: dict, allowed_columns: frozenset[str]) -> pd.Series:
    op = condition.get("op")
    if op not in _ALLOWED_OPS - {"and"}:
        raise InvalidParameterError(f"不支持的 where 操作: {op!r}", param="where")

    if op == "and":
        conditions = condition.get("conditions")
        if not isinstance(conditions, list) or not conditions:
            raise InvalidParameterError("and 需要非空 conditions 列表", param="where")
        mask = pd.Series(True, index=df.index)
        for sub in conditions:
            mask &= _apply_condition(df, sub, allowed_columns)
        return mask

    field = condition.get("field")
    if not field or not isinstance(field, str):
        raise InvalidParameterError("条件需要 string 类型 field", param="where")
    _validate_field(field, allowed_columns)

    value = condition.get("value")
    series = df[field]

    if op == "eq":
        return series == value
    if op == "in":
        if not isinstance(value, (list, tuple, set)):
            raise InvalidParameterError("in 操作的 value 须为列表", param="where")
        return series.isin(list(value))
    if op == "gte":
        return series >= value
    if op == "lte":
        return series <= value

    raise InvalidParameterError(f"未处理的 where 操作: {op!r}", param="where")


def apply_where(df: pd.DataFrame, where: dict | None, allowed_columns: list[str]) -> pd.DataFrame:
    """应用安全 where DSL；字段须在 allowed_columns 白名单内。"""
    if not where:
        return df
    allowed = frozenset(allowed_columns)
    mask = _apply_condition(df, where, allowed)
    return df.loc[mask].copy()

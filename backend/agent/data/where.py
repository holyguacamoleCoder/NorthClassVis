from __future__ import annotations

from typing import Any

import pandas as pd

from .column_aliases import resolve_column
from .exceptions import InvalidParameterError

_ALLOWED_OPS = frozenset({"eq", "in", "gte", "lte", "and"})
_WEEK_FIELD_TOKENS = frozenset({"week", "week_index"})

# Common LLM aliases → canonical op (before validation).
_OP_ALIASES: dict[str, str] = {
    "==": "eq",
    "=": "eq",
    "equals": "eq",
    "equal": "eq",
    "eq": "eq",
    "in": "in",
    "in_list": "in",
    "includes": "in",
    "gte": "gte",
    "ge": "gte",
    ">=": "gte",
    "gt": "gte",
    "greater_than": "gte",
    "greater_than_or_equal": "gte",
    "lte": "lte",
    "le": "lte",
    "<=": "lte",
    "lt": "lte",
    "less_than": "lte",
    "less_than_or_equal": "lte",
    "and": "and",
    "AND": "and",
    "between": "between",  # expanded to and below
}


def repair_where(where: Any) -> tuple[dict[str, Any] | None, list[str]]:
    """
    Coerce common malformed where clauses from the model before normalize_where.
    Returns (repaired dict or None, notes for meta.normalization_notes).
    """
    notes: list[str] = []
    if where is None:
        return None, notes
    if isinstance(where, list):
        items = [repair_where_clause(item, notes) for item in where if item is not None]
        items = [x for x in items if x is not None]
        if not items:
            return None, notes
        if len(items) == 1:
            return items[0], notes
        notes.append("已将 where 数组规范为 {op: and, conditions: [...]}。")
        return {"op": "and", "conditions": items}, notes
    if not isinstance(where, dict):
        raise InvalidParameterError("where 须为 object 或条件数组", param="where")
    repaired = repair_where_clause(where, notes)
    return repaired, notes


def repair_where_clause(clause: Any, notes: list[str]) -> dict[str, Any] | None:
    if clause is None:
        return None
    if not isinstance(clause, dict):
        raise InvalidParameterError("where 条件须为 object", param="where")

    raw = dict(clause)
    if "filters" in raw and "conditions" not in raw:
        raw["conditions"] = raw.pop("filters")
        notes.append("已将 where.filters 规范为 conditions。")
    if "conditions" in raw and "op" not in raw:
        raw["op"] = "and"
        notes.append("已为含 conditions 的 where 补充 op: and。")

    op_raw = raw.get("op")
    if op_raw is None and raw.get("operator") is not None:
        op_raw = raw.pop("operator")
        notes.append("已将 where.operator 规范为 op。")
    if op_raw is None and raw.get("field") and "value" in raw:
        op_raw = "eq"
        notes.append("已补充缺失的 where.op，默认为 eq。")

    op_key = str(op_raw).strip() if op_raw is not None else ""
    if op_key.lower() == "or":
        raise InvalidParameterError(
            "where 不支持 op: or；请改用 op: and 组合条件，或拆分多次 query_data。",
            param="where",
        )
    op_norm = _OP_ALIASES.get(op_key) or _OP_ALIASES.get(op_key.lower()) if op_key else None

    if op_norm == "between":
        field = raw.get("field") or raw.get("field_name")
        value = raw.get("value")
        if isinstance(field, str) and isinstance(value, (list, tuple)) and len(value) >= 2:
            lo, hi = value[0], value[1]
            notes.append("已将 where op:between 展开为 gte/lte 组合。")
            return {
                "op": "and",
                "conditions": [
                    {"field": field, "op": "gte", "value": lo},
                    {"field": field, "op": "lte", "value": hi},
                ],
            }

    if op_norm == "and" or (raw.get("conditions") and op_norm in (None, "and")):
        op_norm = "and"
        conditions_in = raw.get("conditions") or raw.get("filters") or []
        if not isinstance(conditions_in, list):
            raise InvalidParameterError("and 需要 conditions 数组", param="where")
        children: list[dict[str, Any]] = []
        for sub in conditions_in:
            child = repair_where_clause(sub, notes)
            if child is not None:
                children.append(child)
        if not children:
            return None
        if len(children) == 1:
            return children[0]
        return {"op": "and", "conditions": children}

    if op_norm is None and op_key:
        raise InvalidParameterError(
            f"不支持的 where 操作: {op_raw!r}（允许: eq, in, gte, lte, and；"
            '单条件示例: {"field":"major","op":"eq","value":"J23517"}）',
            param="where",
        )
    if op_norm is None:
        raise InvalidParameterError(
            'where 缺少 op（允许: eq, in, gte, lte, and）。'
            '示例: {"field":"student_ID","op":"eq","value":"..."}',
            param="where",
        )

    field = raw.get("field") or raw.get("field_name")
    if field is not None and raw.get("field_name") and not raw.get("field"):
        notes.append("已将 where.field_name 规范为 field。")
    if isinstance(field, str):
        out: dict[str, Any] = {"op": op_norm, "field": field}
        if op_norm == "in" and "values" in raw and "value" not in raw:
            out["value"] = raw["values"]
            notes.append("已将 where.values 规范为 value（in 列表）。")
        elif "value" in raw:
            out["value"] = raw["value"]
        elif op_norm != "in":
            raise InvalidParameterError(
                f"where 条件缺少 value（field={field!r}, op={op_norm}）",
                param="where",
            )
        else:
            raise InvalidParameterError(
                f"where in 操作需要 value 列表（field={field!r}）",
                param="where",
            )
        return out

    raise InvalidParameterError(
        "where 叶子条件需要 string 类型 field 与 op",
        param="where",
    )


def _week_field_token(field: str) -> str:
    from .column_aliases import normalize_identifier

    return normalize_identifier(field)


def _raise_week_on_submit_record(field: str) -> None:
    raise InvalidParameterError(
        f"submit_record 无 {field!r} 列。按周次分析请改用 resource=week_aggregation，"
        "传 classes 与 week_range=[start,end]，或对 week_index 使用 where "
        '(例: {"op":"and","conditions":[{"field":"week_index","op":"gte","value":13},...]})。',
        param="where",
    )


def _normalize_leaf_field(
    field: str,
    *,
    resource: str | None,
    allowed_columns: list[str],
) -> tuple[str, str | None]:
    token = _week_field_token(field)
    if resource == "submit_record" and token in _WEEK_FIELD_TOKENS:
        if "week_index" not in allowed_columns:
            _raise_week_on_submit_record(field)

    resolved = resolve_column(field, allowed_columns)
    if resolved:
        note = f"where.field {field!r} 已规范为 {resolved!r}" if resolved != field else None
        return resolved, note

    if token in _WEEK_FIELD_TOKENS and resource == "week_aggregation":
        raise InvalidParameterError(
            f"where 字段 {field!r} 无法映射；week_aggregation 请使用 week_index 或传 week_range。",
            param="where",
        )

    raise InvalidParameterError(
        f"where 字段 {field!r} 不在 resource 白名单内",
        param="where",
    )


def normalize_where(
    where: dict[str, Any] | None,
    *,
    resource: str | None,
    allowed_columns: list[str],
) -> tuple[dict[str, Any] | None, list[str]]:
    """Normalize where DSL field names (e.g. week → week_index) before apply_where."""
    if not where:
        return None, []

    where, repair_notes = repair_where(where)
    if not where:
        return None, repair_notes

    if not isinstance(where, dict):
        raise InvalidParameterError("where 须为 object", param="where")

    op = where.get("op")
    if op == "and":
        conditions = where.get("conditions")
        if not isinstance(conditions, list) or not conditions:
            raise InvalidParameterError("and 需要非空 conditions 列表", param="where")
        normalized: list[dict[str, Any]] = []
        notes: list[str] = []
        for sub in conditions:
            if not isinstance(sub, dict):
                raise InvalidParameterError("and conditions 项须为 object", param="where")
            norm_sub, sub_notes = normalize_where(
                sub,
                resource=resource,
                allowed_columns=allowed_columns,
            )
            if norm_sub is not None:
                normalized.append(norm_sub)
            notes.extend(sub_notes)
        return {"op": "and", "conditions": normalized}, repair_notes + notes

    if op not in _ALLOWED_OPS - frozenset({"and"}):
        raise InvalidParameterError(
            f"不支持的 where 操作: {op!r}（允许: eq, in, gte, lte, and）",
            param="where",
        )

    field = where.get("field")
    if not field or not isinstance(field, str):
        raise InvalidParameterError("条件需要 string 类型 field", param="where")

    canonical, note = _normalize_leaf_field(
        field,
        resource=resource,
        allowed_columns=allowed_columns,
    )
    out = dict(where)
    out["field"] = canonical
    notes = repair_notes + ([note] if note else [])
    return out, notes


def _validate_field(field: str, allowed_columns: frozenset[str]) -> None:
    if field not in allowed_columns:
        raise InvalidParameterError(
            f"where 字段 {field!r} 不在 resource 白名单内",
            param="where",
        )


def _apply_condition(df: pd.DataFrame, condition: dict, allowed_columns: frozenset[str]) -> pd.Series:
    op = condition.get("op")
    if op not in _ALLOWED_OPS:
        raise InvalidParameterError(
            f"不支持的 where 操作: {op!r}（允许: eq, in, gte, lte, and）",
            param="where",
        )

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


def apply_where(
    df: pd.DataFrame,
    where: dict | None,
    allowed_columns: list[str],
    *,
    resource: str | None = None,
) -> tuple[pd.DataFrame, list[str]]:
    """应用安全 where DSL；字段须在 allowed_columns 白名单内。"""
    if not where:
        return df, []

    where, notes = normalize_where(where, resource=resource, allowed_columns=allowed_columns)
    allowed = frozenset(allowed_columns)
    mask = _apply_condition(df, where, allowed)
    return df.loc[mask].copy(), notes

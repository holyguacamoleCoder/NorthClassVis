"""Post-query/aggregate meta warnings and metric hints for the model."""

from __future__ import annotations

from typing import Any

from .result_store import load_result

_LIMIT_ZERO_MSG = "limit=0 会返回 0 行。全量统计请省略 limit；仅需预览时请使用 limit≥1。"


def reject_limit_zero(limit: int | None) -> None:
    from .exceptions import InvalidParameterError

    if limit is not None and limit == 0:
        raise InvalidParameterError(_LIMIT_ZERO_MSG, param="limit")


def _load_input_meta(inp: dict[str, Any] | None) -> dict[str, Any]:
    if not inp:
        return {}
    ref = inp.get("result_ref")
    if not ref:
        return {}
    try:
        payload = load_result(str(ref))
        return dict(payload.get("meta") or {})
    except (FileNotFoundError, OSError, TypeError, ValueError):
        return {}


def enrich_query_payload(
    payload: dict[str, Any],
    *,
    resource: str,
    group_by: list[str] | None,
    limit: int | None,
) -> None:
    meta = payload.setdefault("meta", {})
    warnings: list[str] = list(meta.get("warnings") or [])
    rows = payload.get("rows") or []
    scanned = int(meta.get("rows_scanned") or 0)

    if group_by and not rows and scanned > 0:
        warnings.append(
            "GROUP_BY_EMPTY: 已扫描行但分组结果为空；请检查 limit、where，全量统计请省略 limit。"
        )
    if meta.get("truncated"):
        warnings.append(
            "TRUNCATED: 结果已截断；需要全量 count/mean 时请省略 limit 后重新 query_data，再 aggregate。"
        )
    else:
        meta["limit_hint"] = "全量统计请省略 limit（不要传 limit:0）。"

    if resource == "submit_record":
        meta["metric_hint"] = (
            "count 统计的是行数（提交次数）；各专业「选课人数/学生数」请用 "
            "aggregate_data 的 count_distinct，field=student_ID，并按 major 分组。"
        )
    elif resource == "student_info":
        meta["metric_hint"] = (
            "student_info 无 class 列；按班统计请用 submit_record + classes，勿仅靠 classes 过滤本表。"
        )

    ui_n = meta.get("ui_selected_students")
    if ui_n is not None:
        meta["scope_hint"] = (
            f"已按可视化面板选中 {ui_n} 名学生过滤（student_ID）。"
            "统计人数请对该结果 aggregate count_distinct(student_ID)，勿用未过滤的全班数据。"
        )

    if warnings:
        meta["warnings"] = warnings


def enrich_aggregate_payload(
    payload: dict[str, Any],
    *,
    metrics: list[dict[str, str]],
    input_spec: dict[str, Any] | None,
    ref_corrected: bool = False,
    ref_corrected_from: str | None = None,
    binding_decision: str | None = None,
) -> None:
    meta = payload.setdefault("meta", {})
    warnings: list[str] = list(meta.get("warnings") or [])
    if binding_decision:
        meta.setdefault("binding_decision", binding_decision)
    if ref_corrected:
        notes = list(meta.get("normalization_notes") or [])
        msg = (
            "RESULT_REF_CORRECTED: input.result_ref 与本题口径不一致，"
            "已按 binding 策略替换为更匹配的数据集。"
        )
        if ref_corrected_from:
            msg += f"（原: {ref_corrected_from}）"
        if binding_decision:
            msg += f"（decision={binding_decision}）"
        notes.append(msg)
        meta["normalization_notes"] = notes
        warnings.append(msg)
    source_meta = _load_input_meta(input_spec)

    if source_meta.get("truncated"):
        warnings.append(
            "AGGREGATE_ON_TRUNCATED_INPUT: input 来自截断的 query；全量统计请省略 limit 重新 query 后再聚合。"
        )

    for metric in metrics:
        op = (metric.get("op") or "").lower()
        field = metric.get("field")
        if op == "count" and field == "student_ID":
            warnings.append(
                "COUNT_NOT_DISTINCT: count(student_ID) 仍按行计数；学生人数请用 "
                'op=count_distinct, field=student_ID。'
            )

    if warnings:
        meta["warnings"] = warnings

    meta.setdefault(
        "metric_hint",
        "count_distinct 用于去重计数（如各专业学生数）；count 为行数。",
    )


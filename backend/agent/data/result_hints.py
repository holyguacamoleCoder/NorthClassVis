"""Post-query/aggregate meta warnings and metric hints for the model."""

from __future__ import annotations

from typing import Any

from .column_aliases import RESOURCE_COLUMNS
from .result_store import load_result

_LIMIT_ZERO_MSG = "limit=0 会返回 0 行。全量统计请省略 limit；仅需预览时请使用 limit≥1。"


def reject_limit_zero(limit: int | None) -> None:
    from .exceptions import InvalidParameterError

    if limit is not None and limit == 0:
        raise InvalidParameterError(_LIMIT_ZERO_MSG, param="limit")


def normalize_limit(limit: int | None) -> tuple[int | None, str | None]:
    """Treat limit=0 as omitted (full scan) with a normalization note."""
    if limit is None:
        return None, None
    if limit == 0:
        return None, "limit=0 已自动忽略，等价于省略 limit（全量查询）。"
    return limit, None


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
        full_n = meta.get("full_row_count")
        preview_n = len(rows)
        warnings.append(
            "PREVIEW_ONLY: 预览行数受工具预算限制，不是查询失败或数据缺失。"
            + (f"全量约 {full_n} 行" if full_n is not None else "全量")
            + f"已在 meta.result_ref（当前预览 {preview_n} 行）。"
            "下一步优先：aggregate_data(order_by+limit=K) 取极值；"
            "或 list_datasets 确认 grain=row 的 dataset_id。勿为看全表再次 query_data。"
        )
        meta["truncation_kind"] = "preview_only"
        meta.setdefault(
            "next_actions",
            [
                {
                    "action": "rank_topk",
                    "tool": "aggregate_data",
                    "note": "同一 dataset_id + order_by + limit=K",
                },
                {"action": "avoid", "note": "不要为预览截断重新全量 query_data"},
            ],
        )
    else:
        meta["limit_hint"] = "全量统计请省略 limit（不要传 limit:0）。"

    if resource == "submit_record":
        meta["metric_hint"] = (
            "count=提交行数；学生人数用 count_distinct(student_ID)。"
            "正确率勿跨表 join：本表已含 full_score（题目满分）与 score_rate（score/full_score）。"
            "按学生正确率：aggregate_data dimensions=[student_ID]，"
            "metrics=sum(score) 与 sum(full_score)，再用 总分/总满分；"
            "或 mean(score_rate)。排名用 order_by+limit。"
        )
    elif resource == "week_aggregation":
        meta["metric_hint"] = (
            "week_aggregation 列: student_ID, week_index, peak_value, direction。"
            " 班均周趋势用 mean(peak_value) 按 week_index 分组；勿用 week 或 score。"
        )
    elif resource == "student_info":
        meta["metric_hint"] = (
            "student_info 无 class 列；按班统计请用 submit_record + classes，勿仅靠 classes 过滤本表。"
        )

    if meta.get("nav_scope_suppressed"):
        notes = list(meta.get("normalization_notes") or [])
        scope_note = next((n for n in notes if "面板" in n or "用户消息" in n or "查询班级" in n), None)
        meta["scope_hint"] = scope_note or "已忽略面板局部选区，按查询/用户意图全文分析。"
    else:
        ui_n = meta.get("ui_selected_students")
        if ui_n is not None:
            meta["scope_hint"] = (
                f"已按可视化面板选中 {ui_n} 名学生过滤（student_ID）。"
                "统计人数请对该结果 aggregate count_distinct(student_ID)，勿用未过滤的全班数据。"
            )

    if warnings:
        meta["warnings"] = warnings

    from data.dataset_identity import column_names_from_payload

    actual_cols = column_names_from_payload(payload)
    if actual_cols:
        meta["columns"] = actual_cols
    resource_cols = RESOURCE_COLUMNS.get(resource)
    if resource_cols:
        meta["resource_columns"] = list(resource_cols)


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

    if source_meta.get("truncated") and source_meta.get("truncation_kind") != "preview_only":
        # Only when the *input query* was limit-truncated (incomplete rows on disk).
        if source_meta.get("query_limit") is not None:
            warnings.append(
                "AGGREGATE_ON_LIMITED_INPUT: input 来自带 limit 的 query 切片；"
                "若要全班统计请改用 grain=row 且全量（无 limit）的 dataset_id，勿盲目重查。"
            )
    elif source_meta.get("truncated") and source_meta.get("truncation_kind") == "preview_only":
        warnings.append(
            "INPUT_PREVIEW_ONLY: 上游预览截断不影响 result_ref 全量；"
            "继续用该 dataset_id；排名请 order_by+limit，勿重扫全表。"
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


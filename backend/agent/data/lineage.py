"""Dataset lineage: parent row dataset for aggregate products.

System stores parent_dataset_id / source_result_ref on DatasetRecord;
catalog projects a one-line parent hint for the LLM. Execution paths
(binding / missing-column errors) trust the structured fields only.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from data.dataset_registry import (
    DatasetRecord,
    find_dataset_by_ref,
    get_dataset_record,
    list_datasets,
)


@dataclass(frozen=True)
class LineageLink:
    parent_dataset_id: str | None
    source_result_ref: str | None
    parent_grain: str | None = None
    parent_label: str | None = None
    parent_columns: list[str] | None = None


def resolve_lineage_from_input(
    session_id: str | None,
    inp: dict[str, Any] | None,
) -> LineageLink:
    """Resolve upstream dataset from aggregate input (dataset_id or result_ref)."""
    if not inp or not session_id:
        return LineageLink(None, None)

    parent: DatasetRecord | None = None
    ds_id = inp.get("dataset_id") or inp.get("chain_from_dataset_id")
    if ds_id:
        parent = get_dataset_record(session_id, str(ds_id))

    ref = inp.get("result_ref")
    source_ref = str(ref).strip().replace("\\", "/") if ref else None
    if parent is None and source_ref:
        parent = find_dataset_by_ref(session_id, source_ref)

    if parent is None:
        return LineageLink(None, source_ref)

    return LineageLink(
        parent_dataset_id=parent.dataset_id,
        source_result_ref=source_ref or parent.result_ref,
        parent_grain=parent.grain,
        parent_label=parent.label,
        parent_columns=list(parent.columns or parent.select_cols or []) or None,
    )


def fields_needed(
    metrics: list[dict[str, Any]] | None,
    dimensions: list[str] | None,
) -> set[str]:
    needed: set[str] = set(dimensions or [])
    for m in metrics or []:
        field = m.get("field")
        if field:
            needed.add(str(field))
    return needed


def missing_fields_on_columns(
    columns: list[str] | None,
    metrics: list[dict[str, Any]] | None,
    dimensions: list[str] | None,
) -> list[str]:
    """Return requested fields not present in dataset columns (exact name match)."""
    if columns is None:
        return []
    available = set(columns)
    # empty columns list means unknown — do not gate
    if not available:
        return []
    missing = [f for f in sorted(fields_needed(metrics, dimensions)) if f not in available]
    return missing


def _rec_covers(rec: DatasetRecord, needed: set[str]) -> bool:
    cols = set(rec.columns or rec.select_cols or [])
    return bool(cols) and needed <= cols


def _link_from_rec(rec: DatasetRecord, *, source_ref: str | None = None) -> LineageLink:
    return LineageLink(
        parent_dataset_id=rec.dataset_id,
        source_result_ref=source_ref or rec.result_ref,
        parent_grain=rec.grain,
        parent_label=rec.label,
        parent_columns=list(rec.columns or rec.select_cols or []) or None,
    )


def walk_parent_chain_for_columns(
    session_id: str,
    start_dataset_id: str,
    missing: list[str],
    *,
    max_hops: int = 8,
) -> LineageLink | None:
    """Walk parent_dataset_id chain until a dataset covers ``missing`` fields."""
    needed = set(missing)
    seen: set[str] = set()
    cur: str | None = start_dataset_id
    hops = 0
    while cur and cur not in seen and hops < max_hops:
        seen.add(cur)
        hops += 1
        rec = get_dataset_record(session_id, cur)
        if rec is None:
            break
        if _rec_covers(rec, needed):
            return _link_from_rec(rec)
        cur = rec.parent_dataset_id
    return None


def prefer_row_parent_for_missing(
    session_id: str | None,
    *,
    bound_dataset_id: str | None,
    missing: list[str],
) -> LineageLink | None:
    """Find an ancestor (or sibling row) that covers missing columns."""
    if not session_id or not missing:
        return None
    needed = set(missing)
    rec = get_dataset_record(session_id, bound_dataset_id) if bound_dataset_id else None

    if rec is not None:
        # Row that lacks columns (e.g. narrow select): try another covering row.
        if (rec.grain or "row") == "row" and not _rec_covers(rec, needed):
            return _newest_row_covering(session_id, missing, exclude_id=rec.dataset_id)

        walk_start = rec.parent_dataset_id
        if walk_start:
            hit = walk_parent_chain_for_columns(session_id, walk_start, missing)
            if hit:
                return hit
        if (rec.grain or "") == "agg":
            return _newest_row_covering(session_id, missing, exclude_id=rec.dataset_id)
        return None

    return _newest_row_covering(session_id, missing)


def _newest_row_covering(
    session_id: str,
    missing: list[str],
    *,
    exclude_id: str | None = None,
) -> LineageLink | None:
    needed = set(missing)
    for rec in reversed(list_datasets(session_id, tail=50)):
        if exclude_id and rec.dataset_id == exclude_id:
            continue
        if (rec.grain or "row") != "row":
            continue
        if _rec_covers(rec, needed):
            return _link_from_rec(rec)
    for rec in reversed(list_datasets(session_id, tail=50)):
        if exclude_id and rec.dataset_id == exclude_id:
            continue
        if (rec.grain or "row") == "row":
            return _link_from_rec(rec)
    return None


def format_missing_column_redirect(
    *,
    base_error: str,
    link: LineageLink | None,
    missing: list[str],
    bound_grain: str | None = None,
) -> tuple[str, str]:
    """Return (next_tool, example) for aggregate missing-column errors."""
    if link and link.parent_dataset_id:
        cols_note = ""
        if link.parent_columns:
            preview = ",".join(link.parent_columns[:8])
            cols_note = f"，cols=[{preview}]"
        grain = link.parent_grain or "row"
        label = link.parent_label or ""
        next_tool = "aggregate_data(input.dataset_id=parent)"
        example = (
            f"缺列 {missing}：当前输入是聚合表，请改用上游 "
            f"dataset_id={link.parent_dataset_id}（grain={grain}"
            + (f"，{label}" if label else "")
            + f"{cols_note}）。"
            "勿因缺列重新 query_data；仅当班级/周次/过滤条件变化时才重查。"
        )
        return next_tool, example

    if (bound_grain or "row") == "row":
        next_tool = "list_datasets 或扩 select 再 query_data"
        example = (
            f"缺列 {missing}：当前 grain=row 结果可能 select 过窄。"
            "请 list_datasets 换一份含这些列的原始行，或对同一口径扩 select 后 query_data"
            "（不是换班级/周次的盲目重查）。"
        )
        return next_tool, example

    next_tool = "list_datasets → aggregate_data(grain=row)"
    example = (
        f"缺列 {missing}：请 list_datasets 选 grain=row 且含这些列的 dataset_id，"
        "再 aggregate_data；勿默认重新 query_data。"
    )
    return next_tool, example


def lineage_redirect_message(
    *,
    dataset_id: str,
    missing: list[str],
    link: LineageLink | None,
) -> str:
    """Binding-gate error when bound dataset lacks required columns."""
    if link and link.parent_dataset_id:
        return (
            f"Error: dataset_id={dataset_id!r} 缺少列 {missing}（多为 grain=agg）。"
            f"请改用上游 parent={link.parent_dataset_id}"
            f"（grain={link.parent_grain or 'row'}）再 aggregate_data。"
            "勿重新 query_data，除非口径（班级/周次/条件）已变。"
        )
    return (
        f"Error: dataset_id={dataset_id!r} 缺少列 {missing}。"
        "请 list_datasets 选 grain=row 且含这些列的 dataset_id；"
        "勿默认重新 query_data。"
    )

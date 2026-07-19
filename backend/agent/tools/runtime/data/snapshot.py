"""Query result snapshots: working set + disk catalog."""

from __future__ import annotations

import json
import time
from typing import Any

from data.dataset_registry import DatasetRecord, append_dataset, new_dataset_id
from loop_state import AnalysisToolContext, QuerySnapshot


def working_result_ref(
    batch_snapshots: list[QuerySnapshot],
    analysis_context: AnalysisToolContext | None,
) -> str | None:
    """本回合最后一次 query 的 ref（仅供提示，不作跨 turn 自动绑定）。"""
    if batch_snapshots:
        return batch_snapshots[-1].result_ref
    if analysis_context and analysis_context.working_active_ref:
        return analysis_context.working_active_ref
    return None


def record_query_result(
    tool_result: str,
    *,
    parsed_args: dict[str, Any] | None = None,
    analysis_context: AnalysisToolContext | None = None,
    batch_snapshots: list[QuerySnapshot],
    tool_name: str | None = None,
) -> str | None:
    if not tool_result or tool_result.startswith("Error:"):
        return None
    try:
        payload = json.loads(tool_result)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    meta = payload.get("meta") or {}
    ref = meta.get("result_ref")
    if not ref:
        return None

    query_limit = _limit_from_args_or_meta(parsed_args, payload)
    stored_rows = _stored_row_count(payload, str(ref))
    reused = bool(meta.get("reused"))
    dataset_id = str(meta.get("dataset_id") or "") or None
    if not dataset_id:
        dataset_id = new_dataset_id()

    from data.dataset_identity import (
        build_dataset_label,
        column_names_from_payload,
        infer_grain,
    )

    grain = infer_grain(tool_name=tool_name, parsed_args=parsed_args, payload=payload)
    columns = column_names_from_payload(payload)
    if not columns and isinstance(parsed_args, dict) and parsed_args.get("select"):
        columns = [str(c) for c in parsed_args["select"] if str(c).strip()]
    dimensions = None
    if isinstance(parsed_args, dict) and parsed_args.get("dimensions"):
        dimensions = [str(d) for d in parsed_args["dimensions"] if str(d).strip()]
    elif meta.get("dimensions"):
        dimensions = [str(d) for d in meta["dimensions"]]

    snap = QuerySnapshot(
        result_ref=str(ref),
        result_rows=stored_rows,
        query_limit=query_limit,
        rows_scanned=_safe_int(meta.get("rows_scanned")),
        resource=meta.get("resource") or payload.get("resource"),
        dataset_id=dataset_id,
    )
    batch_snapshots.append(snap)

    if analysis_context is not None:
        analysis_context.register_query_snapshot(snap)
        classes = None
        if parsed_args:
            c = parsed_args.get("classes") or parsed_args.get("class")
            if isinstance(c, list):
                classes = c
            elif c:
                classes = [str(c)]
        label = build_dataset_label(
            grain=grain,
            resource=snap.resource,
            classes=classes,
            parsed_args=parsed_args,
            columns=columns,
            dimensions=dimensions,
            result_rows=snap.result_rows,
            query_limit=snap.query_limit,
        )
        parent_dataset_id = None
        source_result_ref = None
        if (grain == "agg" or tool_name == "enrich_data") and isinstance(parsed_args, dict):
            from data.lineage import resolve_lineage_from_input

            link = resolve_lineage_from_input(
                analysis_context.session_id,
                parsed_args.get("input") if isinstance(parsed_args.get("input"), dict) else parsed_args,
            )
            if link.parent_dataset_id is None and (
                parsed_args.get("dataset_id") or parsed_args.get("result_ref")
            ):
                link = resolve_lineage_from_input(analysis_context.session_id, parsed_args)
            parent_dataset_id = link.parent_dataset_id
            source_result_ref = link.source_result_ref
            if parent_dataset_id is None and isinstance(parsed_args.get("input"), dict):
                inp = parsed_args["input"]
                if inp.get("dataset_id"):
                    parent_dataset_id = str(inp["dataset_id"])
                if inp.get("result_ref"):
                    source_result_ref = str(inp["result_ref"]).strip().replace("\\", "/")
        if not reused:
            from data.query_reuse import build_query_fingerprints

            exact_fp = meta.get("query_fingerprint")
            core_fp = meta.get("query_core_fingerprint")
            select_cols = meta.get("select_cols")
            if (
                not exact_fp
                and parsed_args is not None
                and grain == "row"
                and tool_name == "query_data"
            ):
                exact_fp, core_fp, select_cols, _lim = build_query_fingerprints(
                    resource=str(snap.resource or parsed_args.get("resource") or ""),
                    resolve_params={
                        k: parsed_args.get(k)
                        for k in ("class", "classes", "majors", "week_range", "student_ids")
                        if parsed_args.get(k) is not None
                    },
                    where=parsed_args.get("where") or parsed_args.get("filter"),
                    select=parsed_args.get("select"),
                    group_by=parsed_args.get("group_by"),
                    order_by=parsed_args.get("order_by"),
                    limit=query_limit,
                )
            append_dataset(
                analysis_context.session_id,
                DatasetRecord(
                    dataset_id=dataset_id,
                    result_ref=snap.result_ref,
                    user_turn=analysis_context.user_turn,
                    resource=snap.resource,
                    result_rows=snap.result_rows,
                    query_limit=snap.query_limit,
                    rows_scanned=snap.rows_scanned,
                    classes=classes,
                    created_at=time.time(),
                    query_fingerprint=exact_fp,
                    query_core_fingerprint=core_fp,
                    select_cols=select_cols or columns or None,
                    grain=grain,
                    label=label,
                    columns=columns or None,
                    dimensions=dimensions,
                    parent_dataset_id=parent_dataset_id,
                    source_result_ref=source_result_ref,
                ),
            )
        meta_out = payload.setdefault("meta", {})
        meta_out["dataset_id"] = dataset_id
        meta_out["storage_layer"] = "disk"
        meta_out["working_ref"] = snap.result_ref
        meta_out["grain"] = grain
        meta_out["label"] = label
        if columns:
            meta_out["columns"] = columns
        if dimensions:
            meta_out["dimensions"] = dimensions
        if parent_dataset_id:
            meta_out["parent_dataset_id"] = parent_dataset_id
        if source_result_ref:
            meta_out["source_result_ref"] = source_result_ref
            meta_out["input_result_ref"] = source_result_ref
    return json.dumps(payload, ensure_ascii=False, default=str)


def _limit_from_args_or_meta(
    parsed_args: dict[str, Any] | None,
    payload: dict,
) -> int | None:
    if parsed_args is not None and parsed_args.get("limit") is not None:
        try:
            raw = int(parsed_args["limit"])
            if raw == 0:
                return None
            return raw
        except (TypeError, ValueError):
            pass
    meta = payload.get("meta") or {}
    if meta.get("query_limit") is not None:
        try:
            return int(meta["query_limit"])
        except (TypeError, ValueError):
            pass
    return None


def _stored_row_count(payload: dict, ref: str) -> int:
    rows = payload.get("rows")
    preview_rows = len(rows) if isinstance(rows, list) else 0
    meta = payload.get("meta") or {}
    if not meta.get("truncated"):
        return preview_rows
    try:
        from data.result_store import load_result

        full = load_result(ref)
        return len(full.get("rows") or [])
    except (FileNotFoundError, OSError, TypeError, ValueError):
        return preview_rows


def _safe_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None

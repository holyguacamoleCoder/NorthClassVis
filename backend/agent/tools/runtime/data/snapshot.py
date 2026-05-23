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
) -> str | None:
    if not tool_result or tool_result.startswith("Error:"):
        return None
    try:
        payload = json.loads(tool_result)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    ref = (payload.get("meta") or {}).get("result_ref")
    if not ref:
        return None

    query_limit = _limit_from_args_or_meta(parsed_args, payload)
    meta = payload.get("meta") or {}
    stored_rows = _stored_row_count(payload, str(ref))

    dataset_id = new_dataset_id()
    snap = QuerySnapshot(
        result_ref=str(ref),
        result_rows=stored_rows,
        query_limit=query_limit,
        rows_scanned=_safe_int(meta.get("rows_scanned")),
        resource=meta.get("resource"),
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
            ),
        )
        meta_out = payload.setdefault("meta", {})
        meta_out["dataset_id"] = dataset_id
        meta_out["storage_layer"] = "disk"
        meta_out["working_ref"] = snap.result_ref
    return json.dumps(payload, ensure_ascii=False, default=str)


def _limit_from_args_or_meta(
    parsed_args: dict[str, Any] | None,
    payload: dict,
) -> int | None:
    if parsed_args is not None and parsed_args.get("limit") is not None:
        try:
            return int(parsed_args["limit"])
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

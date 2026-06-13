"""Judge online aggregate_data binding against scenario expectations."""

from __future__ import annotations

import json
import re
from typing import Any

from data.dataset_registry import DatasetRecord, find_dataset_by_ref

_SLICE_MAX_ROWS = 50
_BROAD_MIN_ROWS = 500
_CROSS_TURN_ERROR_MARKERS = ("上一轮", "不能自动续用")
_PERMISSION_MARKERS = ("permission denied", "模式限制", "不可用")


def _norm_ref(ref: str | None) -> str:
    return (ref or "").strip().replace("\\", "/")


def _bound_ref_and_dataset_id(
    meta: dict[str, Any],
    tool_input: dict[str, Any] | None,
) -> tuple[str | None, str | None]:
    """Resolve the *source query* ref/id bound for aggregate (not aggregate output ref)."""
    trace = meta.get("binding_trace") if isinstance(meta.get("binding_trace"), dict) else {}
    bound_ref = trace.get("bound_result_ref") if isinstance(trace, dict) else None
    bound_ds = trace.get("bound_dataset_id") if isinstance(trace, dict) else None
    if bound_ref or bound_ds:
        return (
            str(bound_ref) if bound_ref else None,
            str(bound_ds) if bound_ds else None,
        )

    dataset_id: str | None = None
    ref: str | None = None
    if isinstance(tool_input, dict):
        inp = tool_input.get("input")
        if isinstance(inp, dict):
            ref = inp.get("result_ref")
            dataset_id = inp.get("dataset_id")
        if not dataset_id:
            dataset_id = tool_input.get("dataset_id")
    if isinstance(trace, dict):
        ref = ref or trace.get("result_ref")
        dataset_id = dataset_id or trace.get("dataset_id")
    dataset_id = dataset_id or meta.get("dataset_id")
    # aggregate output meta.result_ref points at aggregate artifact — use only as last resort
    ref = ref or meta.get("source_result_ref") or meta.get("input_result_ref")

    # Binding pipeline may override the model's stale/wrong ref — do not judge by LLM input alone.
    if meta.get("ref_corrected") and not (bound_ref or bound_ds):
        ref = None
        dataset_id = None

    return (str(ref) if ref else None, str(dataset_id) if dataset_id else None)


def _catalog_record(
    meta: dict[str, Any],
    catalog: list[DatasetRecord],
    *,
    tool_input: dict[str, Any] | None = None,
) -> DatasetRecord | None:
    ref, dataset_id = _bound_ref_and_dataset_id(meta, tool_input)
    session_id = meta.get("session_id")

    if dataset_id:
        for rec in reversed(catalog):
            if rec.dataset_id == dataset_id:
                return rec

    if ref:
        rec = find_dataset_by_ref(session_id, ref)
        if rec:
            return rec
        for item in reversed(catalog):
            if _norm_ref(item.result_ref) == _norm_ref(ref):
                return item

    # Fallback: infer slice/broad from aggregate meta rows_scanned (source row count)
    scanned = meta.get("rows_scanned")
    if scanned is not None:
        return DatasetRecord(
            dataset_id=dataset_id or "inferred",
            result_ref=ref or "",
            user_turn=int(meta.get("user_turn") or 0),
            result_rows=int(scanned),
            query_limit=meta.get("query_limit"),
            rows_scanned=meta.get("rows_scanned_full") or int(scanned),
        )
    return None


def _is_slice(rec: DatasetRecord) -> bool:
    if rec.result_rows > _SLICE_MAX_ROWS:
        return False
    if rec.query_limit is not None:
        return True
    scanned = rec.rows_scanned
    if scanned is None:
        return rec.result_rows <= _SLICE_MAX_ROWS
    if scanned >= max(rec.result_rows * 10, _BROAD_MIN_ROWS):
        return True
    # aggregate meta often reports source row count only (scanned == rows)
    if scanned == rec.result_rows and rec.result_rows <= _SLICE_MAX_ROWS:
        return True
    return False


def _is_broad(rec: DatasetRecord) -> bool:
    if rec.result_rows > _BROAD_MIN_ROWS:
        return True
    if rec.query_limit is None and rec.result_rows > _SLICE_MAX_ROWS:
        scanned = rec.rows_scanned
        if scanned is None:
            return True
        return scanned == rec.result_rows or scanned > _BROAD_MIN_ROWS
    return False


def recover_meta_from_partial_json(content: str) -> dict[str, Any]:
    """Best-effort meta when tool JSON in history is truncated (persist preview)."""
    text = content or ""
    meta: dict[str, Any] = {}
    m = re.search(r'"rows_scanned"\s*:\s*(\d+)', text)
    if m:
        meta["rows_scanned"] = int(m.group(1))
    m = re.search(r'"binding_decision"\s*:\s*"([^"]+)"', text)
    if m:
        meta["binding_decision"] = m.group(1)
    m = re.search(r'"dataset_id"\s*:\s*"([^"]+)"', text)
    if m:
        meta["dataset_id"] = m.group(1)
    m = re.search(r'"bound_result_ref"\s*:\s*"([^"]+)"', text)
    if m:
        trace = meta.setdefault("binding_trace", {})
        if isinstance(trace, dict):
            trace["bound_result_ref"] = m.group(1)
    m = re.search(r'"bound_dataset_id"\s*:\s*"([^"]+)"', text)
    if m:
        trace = meta.setdefault("binding_trace", {})
        if isinstance(trace, dict):
            trace["bound_dataset_id"] = m.group(1)
    m = re.search(r'"resolver"\s*:\s*"([^"]+)"', text)
    if m:
        trace = meta.setdefault("binding_trace", {})
        if isinstance(trace, dict):
            trace["resolver"] = m.group(1)
    if meta.get("ref_corrected") is None:
        if '"ref_corrected": true' in text or '"ref_corrected":true' in text:
            meta["ref_corrected"] = True
    return meta


def _parse_aggregate_content(content: str) -> tuple[bool, dict[str, Any]]:
    """Match extract_aggregate_events: Error text or invalid JSON => failure."""
    text = (content or "").strip()
    if not text:
        return False, {}
    if text.startswith("Error:"):
        return False, {}
    if text.lower().startswith("permission denied"):
        return False, {}
    lower = text.lower()
    if any(m in lower for m in _PERMISSION_MARKERS):
        return False, {}
    if any(m in text for m in _CROSS_TURN_ERROR_MARKERS):
        return False, {}
    if not text.startswith("{"):
        return False, {}
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        recovered = recover_meta_from_partial_json(text)
        return (bool(recovered), recovered)
    meta = payload.get("meta")
    return True, dict(meta) if isinstance(meta, dict) else {}


def _is_guard_error(content: str) -> bool:
    """True only for failed tool text, not successful JSON payloads with trace metadata."""
    ok, _ = _parse_aggregate_content(content)
    if ok:
        return False
    text = (content or "").strip()
    if not text:
        return False
    if text.startswith("Error:"):
        return True
    if text.lower().startswith("permission denied"):
        return True
    lower = text.lower()
    if any(m in lower for m in _PERMISSION_MARKERS):
        return True
    if any(m in text for m in _CROSS_TURN_ERROR_MARKERS):
        return True
    if text.startswith("{"):
        return True
    return False


def _slice_from_binding_meta(meta: dict[str, Any]) -> bool:
    decision = str(meta.get("binding_decision") or "")
    if not decision.startswith("chain_slice"):
        return False
    scanned = meta.get("rows_scanned")
    return scanned is not None and int(scanned) <= _SLICE_MAX_ROWS


def _explicit_dataset_id(
    meta: dict[str, Any],
    tool_input: dict[str, Any] | None,
) -> str | None:
    ds = meta.get("dataset_id")
    if isinstance(tool_input, dict):
        inp = tool_input.get("input")
        if isinstance(inp, dict):
            ds = ds or inp.get("dataset_id")
        ds = ds or tool_input.get("dataset_id")
    return str(ds) if ds else None


def _guard_reason(content: str) -> str:
    text = (content or "").strip()
    if any(m in text for m in _CROSS_TURN_ERROR_MARKERS):
        return "cross_turn_guard"
    if any(m in text.lower() for m in _PERMISSION_MARKERS):
        return "permission_deny"
    if text.startswith("Error:"):
        return "aggregate_error"
    return "guard"


def judge_aggregate(
    expect: str,
    *,
    meta: dict[str, Any],
    catalog: list[DatasetRecord],
    content: str = "",
    tool_input: dict[str, Any] | None = None,
    current_user_turn: int | None = None,
    accept_guard_error: bool = False,
) -> tuple[bool, str]:
    """Return (ok, reason)."""
    expect = (expect or "").strip().lower()
    payload_ok, parsed_meta = _parse_aggregate_content(content)
    merged_meta = {**parsed_meta, **meta}
    text = (content or "").strip()
    if merged_meta.get("binding_decision") and merged_meta.get("rows_scanned") is not None:
        payload_ok = True
        is_error = text.startswith("Error:")
    else:
        is_error = _is_guard_error(content)

    if expect == "reject_cross_turn":
        if is_error:
            return True, _guard_reason(content)
        rec = _catalog_record(meta, catalog, tool_input=tool_input)
        if rec and not is_error:
            return False, "expected cross-turn reject but aggregate succeeded"
        return False, "expected cross-turn Error but got success"

    if accept_guard_error and is_error:
        return True, "guard_cross_turn_reject"

    if is_error:
        return False, f"unexpected error: {content[:160]}"

    rec = _catalog_record(merged_meta, catalog, tool_input=tool_input)
    if rec is None:
        if expect == "slice" and _slice_from_binding_meta(merged_meta):
            scanned = int(merged_meta["rows_scanned"])
            return True, f"slice from binding_decision rows_scanned={scanned}"
        return False, "no catalog record for bound ref/dataset_id"

    if expect == "slice":
        if _is_slice(rec):
            return True, f"slice rows={rec.result_rows} limit={rec.query_limit}"
        if _slice_from_binding_meta(merged_meta):
            scanned = int(merged_meta["rows_scanned"])
            return True, f"slice from binding_decision rows_scanned={scanned}"
        return False, f"not slice: rows={rec.result_rows} limit={rec.query_limit}"

    if expect == "broad":
        if _is_broad(rec):
            return True, f"broad rows={rec.result_rows} limit={rec.query_limit}"
        return False, f"not broad: rows={rec.result_rows} limit={rec.query_limit}"

    if expect == "explicit_dataset_id":
        ds = _explicit_dataset_id(merged_meta, tool_input)
        if not ds:
            return False, "missing explicit dataset_id in aggregate input/meta"
        if rec.dataset_id != str(ds):
            return False, f"dataset_id mismatch meta={ds!r} bound={rec.dataset_id!r}"
        return True, f"explicit dataset_id={rec.dataset_id}"

    if expect == "allow_cross_turn_explicit":
        ds = _explicit_dataset_id(merged_meta, tool_input)
        if not ds:
            return False, "cross-turn explicit requires dataset_id"
        if current_user_turn is not None and rec.user_turn >= current_user_turn:
            return False, f"dataset user_turn={rec.user_turn} not prior to current={current_user_turn}"
        return True, f"cross_turn_explicit dataset_id={rec.dataset_id} prior_turn={rec.user_turn}"

    return False, f"unknown expect type: {expect!r}"


def resolver_from_meta(meta: dict[str, Any]) -> str:
    trace = meta.get("binding_trace")
    if isinstance(trace, dict):
        resolver = trace.get("resolver")
        if resolver:
            return str(resolver)
        scope = trace.get("scope")
        if scope:
            return str(scope)
    decision = meta.get("binding_decision")
    if decision:
        text = str(decision)
        for key in ("llm", "heuristic", "explicit", "rule", "chain", "fresh"):
            if key in text.lower():
                return key
        return text
    return "unknown"

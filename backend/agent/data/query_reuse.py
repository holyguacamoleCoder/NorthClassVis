"""Reuse prior query_data results within a session (avoid identical full re-scans)."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from data.dataset_registry import DatasetRecord, list_datasets
from data.result_store import load_result


def _canon_where(where: Any) -> Any:
    """Canonicalize where trees so condition order does not matter under and/or."""
    if not isinstance(where, dict):
        return _canon(where)
    op = where.get("op")
    if op in ("and", "or") and isinstance(where.get("conditions"), list):
        kids = [_canon_where(c) for c in where["conditions"]]
        kids_sorted = sorted(kids, key=lambda x: json.dumps(x, ensure_ascii=False, sort_keys=True))
        return {"op": op, "conditions": kids_sorted}
    return _canon(where)


def _canon(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _canon(value[k]) for k in sorted(value.keys(), key=str)}
    if isinstance(value, (list, tuple)):
        return [_canon(x) for x in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _norm_select(select: list[str] | None) -> list[str] | None:
    if not select:
        return None
    cols = sorted({str(c).strip() for c in select if str(c).strip()})
    return cols or None


def _norm_resolve(resolve: dict[str, Any] | None) -> dict[str, Any]:
    if not resolve:
        return {}
    out: dict[str, Any] = {}
    for key in ("class", "classes", "majors", "week_range", "student_ids"):
        if key not in resolve or resolve[key] is None:
            continue
        val = resolve[key]
        if key in ("classes", "majors", "student_ids") and isinstance(val, (list, tuple)):
            out[key] = sorted(str(x) for x in val)
        elif key == "class":
            out[key] = str(val)
        else:
            out[key] = _canon(val)
    return out


def _norm_limit(limit: int | None) -> int | None:
    if limit is None:
        return None
    try:
        n = int(limit)
    except (TypeError, ValueError):
        return None
    if n == 0:
        return None
    return n


def build_query_fingerprints(
    *,
    resource: str,
    resolve_params: dict[str, Any] | None = None,
    where: dict[str, Any] | None = None,
    select: list[str] | None = None,
    group_by: list[str] | None = None,
    order_by: list[dict] | None = None,
    limit: int | None = None,
) -> tuple[str, str, list[str] | None, int | None]:
    """Return (exact_fp, core_fp, select_cols, limit). core ignores select+limit."""
    resolve = _norm_resolve(resolve_params)
    select_cols = _norm_select(select)
    lim = _norm_limit(limit)
    core_payload = {
        "resource": str(resource or "").strip(),
        "resolve": resolve,
        "where": _canon_where(where) if where else None,
        "group_by": _norm_select(group_by),
        "order_by": _canon(order_by) if order_by else None,
    }
    exact_payload = {
        **core_payload,
        "select": select_cols,
        "limit": lim,
    }
    return (
        _hash_payload(exact_payload),
        _hash_payload(core_payload),
        select_cols,
        lim,
    )


def _hash_payload(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def find_reusable_dataset(
    session_id: str | None,
    *,
    exact_fp: str,
    core_fp: str,
    select_cols: list[str] | None,
    limit: int | None,
) -> DatasetRecord | None:
    """Newest matching catalog row: exact fingerprint, else compatible full-scan."""
    if not session_id:
        return None
    rows = list(reversed(list_datasets(session_id, tail=200)))
    for rec in rows:
        if rec.query_fingerprint and rec.query_fingerprint == exact_fp:
            return rec
    # Compatible: same core, stored full scan, request full scan, select ⊆ stored.
    if limit is not None:
        return None
    for rec in rows:
        if not rec.query_core_fingerprint or rec.query_core_fingerprint != core_fp:
            continue
        if rec.query_limit is not None:
            continue
        stored_select = rec.select_cols
        if select_cols is None:
            if stored_select is None:
                return rec
            continue
        if stored_select is None:
            # Stored kept all projected cols unknown — verify via file columns.
            if _result_has_columns(rec.result_ref, select_cols):
                return rec
            continue
        if set(select_cols).issubset(set(stored_select)):
            return rec
    return None


def _result_has_columns(result_ref: str, cols: list[str]) -> bool:
    try:
        payload = load_result(result_ref)
    except (FileNotFoundError, OSError, json.JSONDecodeError, TypeError, ValueError):
        return False
    headers = payload.get("columns") or []
    names: set[str] = set()
    for col in headers:
        if isinstance(col, dict) and col.get("name"):
            names.add(str(col["name"]))
        elif isinstance(col, str):
            names.add(col)
    return set(cols).issubset(names)


def load_reused_payload(rec: DatasetRecord) -> dict[str, Any] | None:
    try:
        payload = load_result(rec.result_ref)
    except (FileNotFoundError, OSError, json.JSONDecodeError, TypeError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None
    meta = payload.setdefault("meta", {})
    meta["result_ref"] = rec.result_ref
    meta["dataset_id"] = rec.dataset_id
    meta["reused"] = True
    meta["storage_layer"] = "disk"
    if rec.resource:
        meta.setdefault("resource", rec.resource)
        payload.setdefault("resource", rec.resource)
    if rec.query_limit is not None:
        meta["query_limit"] = rec.query_limit
    if rec.rows_scanned is not None:
        meta.setdefault("rows_scanned", rec.rows_scanned)
    if rec.grain:
        meta["grain"] = rec.grain
    if rec.label:
        meta["label"] = rec.label
    if rec.columns:
        meta["columns"] = rec.columns
    if rec.dimensions:
        meta["dimensions"] = rec.dimensions
    meta["reuse_note"] = (
        f"复用本会话已有结果 dataset_id={rec.dataset_id}"
        + (f"（{rec.label}）" if rec.label else "")
        + f" result_ref={rec.result_ref}；未重新全量扫描。"
    )
    return payload

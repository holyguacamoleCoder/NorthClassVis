from __future__ import annotations

from typing import Any

from data.dataset_registry import find_dataset_by_ref, get_dataset_record
from data.result_store import load_result
from loop_state import AnalysisToolContext, QuerySnapshot

from .evidence_cites import (
    EvidenceCite,
    collect_evidence_sources,
    is_result_ref_token,
    normalize_result_ref,
)


def resolve_ds_cite(
    session_id: str | None,
    target: str,
) -> dict[str, Any] | None:
    """
    Resolve [@ds:…] to a catalog dataset_id or a disk-backed result_ref
    (common when aggregate_data UUID is mis-tagged as ds).
    """
    needle = str(target or "").strip()
    if not needle:
        return None

    rec = get_dataset_record(session_id, needle)
    if rec:
        return {
            "verifiable": True,
            "dataset_id": rec.dataset_id,
            "result_ref": rec.result_ref,
            "resource": rec.resource,
            "row_count": rec.result_rows,
        }

    if not is_result_ref_token(needle):
        return None

    ref = normalize_result_ref(needle)
    snap = _snapshot_summary_for_ref(ref)
    if not snap.get("verifiable"):
        return None

    out: dict[str, Any] = dict(snap)
    out["note"] = (
        f"cite 使用了 [@ds:{needle}] 但目标实为 result_ref；"
        f"建议改为 [@ref:{ref}]"
    )
    parent = find_dataset_by_ref(session_id, ref)
    if parent:
        out["dataset_id"] = parent.dataset_id
    return out


def known_ids_from_context(
    analysis_context: AnalysisToolContext | None,
) -> tuple[set[str], set[str]]:
    dataset_ids: set[str] = set()
    result_refs: set[str] = set()
    if analysis_context is None:
        return dataset_ids, result_refs
    for snap in analysis_context.turn_snapshots:
        if snap.dataset_id:
            dataset_ids.add(snap.dataset_id)
        if snap.result_ref:
            result_refs.add(snap.result_ref.strip().replace("\\", "/"))
    if analysis_context.session_id:
        from data.dataset_registry import list_datasets

        for rec in list_datasets(analysis_context.session_id, tail=200):
            dataset_ids.add(rec.dataset_id)
            result_refs.add(rec.result_ref.strip().replace("\\", "/"))
    return dataset_ids, result_refs


def validate_cites_against_session(
    cites: list[EvidenceCite],
    *,
    known_dataset_ids: set[str],
    known_result_refs: set[str],
    validation_level: str = "deliver",
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    level = (validation_level or "deliver").strip().lower()
    strict = level == "strict"
    for cite in cites:
        if cite.kind == "ds":
            if cite.target in known_dataset_ids:
                continue
            if is_result_ref_token(cite.target):
                ref = normalize_result_ref(cite.target)
                norm_ref = ref.replace("\\", "/")
                disk_ok = norm_ref in known_result_refs or _snapshot_summary_for_ref(
                    norm_ref
                ).get("verifiable")
                if disk_ok:
                    warnings.append(
                        f"[@ds:{cite.target}] 实为 result_ref；请改用 [@ref:{ref}]"
                    )
                    continue
            msg = f"unknown dataset_id in cite: {cite.target!r}"
            if strict:
                errors.append(msg)
            else:
                warnings.append(msg)
        elif cite.kind == "ref":
            norm = cite.target.strip().replace("\\", "/")
            if not norm.startswith("query-results/"):
                norm = f"query-results/{norm.lstrip('/')}"
            if norm in known_result_refs:
                continue
            if _snapshot_summary_for_ref(norm).get("verifiable"):
                if strict:
                    warnings.append(
                        f"result_ref {cite.target!r} 未登记于 session catalog，但磁盘可验真"
                    )
                continue
            msg = f"result_ref not in session catalog: {cite.target!r}"
            if strict:
                errors.append(msg)
            else:
                warnings.append(msg)
    return errors, warnings


def _snapshot_summary_for_ref(result_ref: str) -> dict[str, Any]:
    try:
        payload = load_result(result_ref)
    except (FileNotFoundError, OSError, ValueError):
        return {"verifiable": False, "error": "result_ref not on disk"}
    meta = payload.get("meta") or {}
    rows = payload.get("rows") or []
    return {
        "verifiable": True,
        "resource": meta.get("resource"),
        "row_count": len(rows) if isinstance(rows, list) else meta.get("row_count"),
        "result_ref": result_ref,
    }


def build_report_evidence_digest(
    evidence_body: str,
    *,
    session_id: str | None = None,
    turn_snapshots: list[QuerySnapshot] | None = None,
) -> list[dict[str, Any]]:
    """Parse Evidence section cites into verifiable summaries for HTTP report_evidence."""
    cites = collect_evidence_sources(evidence_body)
    known_ds, known_refs = set(), set()
    if turn_snapshots:
        for snap in turn_snapshots:
            if snap.dataset_id:
                known_ds.add(snap.dataset_id)
            if snap.result_ref:
                known_refs.add(snap.result_ref.replace("\\", "/"))

    items: list[dict[str, Any]] = []
    for cite in cites:
        entry: dict[str, Any] = {
            "cite": f"{cite.kind}:{cite.target}",
            "summary": cite.summary or "",
            "verifiable": False,
        }
        if cite.kind == "ds":
            resolved = resolve_ds_cite(session_id, cite.target)
            if resolved:
                entry.update(resolved)
            else:
                entry["error"] = "dataset_id not in session catalog"
        elif cite.kind == "ref":
            norm = cite.target.replace("\\", "/")
            if not norm.startswith("query-results/"):
                norm = f"query-results/{norm.lstrip('/')}"
            snap = _snapshot_summary_for_ref(norm)
            entry.update(snap)
            entry["cite"] = f"ref:{cite.target}"
            if snap.get("verifiable"):
                rec = find_dataset_by_ref(session_id, norm)
                if rec:
                    entry["dataset_id"] = rec.dataset_id
        items.append(entry)
    return items


def digest_from_report_markdown(
    source: str,
    *,
    session_id: str | None = None,
    turn_snapshots: list[QuerySnapshot] | None = None,
) -> list[dict[str, Any]]:
    from .parse import parse_report_markdown

    parsed = parse_report_markdown(source)
    section = parsed.section_map().get("evidence")
    if not section:
        return []
    return build_report_evidence_digest(
        section.body,
        session_id=session_id,
        turn_snapshots=turn_snapshots,
    )

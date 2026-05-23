"""Build binding context for aggregate / intent recognition."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from data.dataset_registry import build_datasets_catalog, get_dataset_record
from loop_state import AnalysisToolContext, QuerySnapshot

from .types import BindingCandidate


@dataclass
class QuerySummary:
    dataset_id: str | None
    result_ref: str
    result_rows: int
    query_limit: int | None
    rows_scanned: int | None
    resource: str | None
    order_in_turn: int


@dataclass
class BindingContext:
    teacher_message: str
    current_user_turn: int
    session_id: str | None
    candidates: list[BindingCandidate]
    query_summaries: list[QuerySummary]
    catalog_datasets: list[dict[str, Any]]
    model_input: dict[str, Any]
    model_metrics: list[dict[str, Any]]
    model_bind: str | None
    model_dimensions: list[str] | None


def _snap_to_candidate(snap: QuerySnapshot, user_turn: int) -> BindingCandidate:
    return BindingCandidate(
        result_ref=snap.result_ref,
        result_rows=snap.result_rows,
        user_turn=user_turn,
        query_limit=snap.query_limit,
        rows_scanned=snap.rows_scanned,
        dataset_id=snap.dataset_id,
        resource=snap.resource,
    )


def collect_turn_candidates(
    analysis_context: AnalysisToolContext | None,
    batch_snapshots: list[QuerySnapshot],
) -> tuple[list[BindingCandidate], list[QuerySummary]]:
    turn = analysis_context.user_turn if analysis_context else 0
    combined = list(analysis_context.turn_snapshots if analysis_context else []) + list(
        batch_snapshots
    )
    ordered: list[QuerySnapshot] = []
    seen: set[str] = set()
    for snap in combined:
        key = snap.result_ref.strip().replace("\\", "/")
        if key in seen:
            ordered = [s for s in ordered if s.result_ref.strip().replace("\\", "/") != key]
        else:
            seen.add(key)
        ordered.append(snap)

    candidates = [_snap_to_candidate(s, turn) for s in ordered]
    summaries = [
        QuerySummary(
            dataset_id=s.dataset_id,
            result_ref=s.result_ref,
            result_rows=s.result_rows,
            query_limit=s.query_limit,
            rows_scanned=s.rows_scanned,
            resource=s.resource,
            order_in_turn=i + 1,
        )
        for i, s in enumerate(ordered)
    ]
    return candidates, summaries


def build_binding_context(
    *,
    inp: dict[str, Any],
    metrics: list[dict[str, Any]],
    dimensions: list[str] | None,
    bind: str | None,
    analysis_context: AnalysisToolContext | None,
    batch_snapshots: list[QuerySnapshot],
) -> BindingContext:
    session_id = analysis_context.session_id if analysis_context else None
    turn = analysis_context.user_turn if analysis_context else 0
    teacher = (analysis_context.current_user_message if analysis_context else None) or ""
    candidates, summaries = collect_turn_candidates(analysis_context, batch_snapshots)
    catalog = build_datasets_catalog(
        session_id,
        tail=30,
        current_user_turn=turn,
    )
    return BindingContext(
        teacher_message=teacher,
        current_user_turn=turn,
        session_id=session_id,
        candidates=candidates,
        query_summaries=summaries,
        catalog_datasets=list(catalog.get("datasets") or []),
        model_input=dict(inp or {}),
        model_metrics=list(metrics or []),
        model_bind=bind,
        model_dimensions=dimensions,
    )


def candidate_for_dataset_id(
    ctx: BindingContext,
    dataset_id: str,
) -> BindingCandidate | None:
    needle = dataset_id.strip()
    for c in ctx.candidates:
        if c.dataset_id == needle:
            return c
    rec = get_dataset_record(ctx.session_id, needle)
    if rec:
        return BindingCandidate(
            result_ref=rec.result_ref,
            result_rows=rec.result_rows,
            user_turn=rec.user_turn,
            query_limit=rec.query_limit,
            rows_scanned=rec.rows_scanned,
            dataset_id=rec.dataset_id,
            resource=rec.resource,
        )
    return None


def catalog_item(ctx: BindingContext, dataset_id: str) -> dict[str, Any] | None:
    for item in ctx.catalog_datasets:
        if item.get("dataset_id") == dataset_id:
            return item
    for item in build_datasets_catalog(ctx.session_id, tail=50).get("datasets") or []:
        if item.get("dataset_id") == dataset_id:
            return item
    return None

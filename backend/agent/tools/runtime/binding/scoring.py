"""Compatibility scoring for aggregate_data input binding."""

from __future__ import annotations

from typing import Any

from data.column_aliases import RESOURCE_COLUMNS

from .types import SLICE_MAX_ROWS, BindMode, BindingCandidate, CROSS_TURN_PENALTY


def _fields_needed(
    metrics: list[dict[str, Any]],
    dimensions: list[str] | None,
) -> set[str]:
    needed: set[str] = set(dimensions or [])
    for m in metrics:
        field = m.get("field")
        if field:
            needed.add(str(field))
    return needed


def _resource_column_set(resource: str | None) -> set[str] | None:
    if not resource:
        return None
    cols = RESOURCE_COLUMNS.get(resource)
    return set(cols) if cols else None


def _resource_field_compatibility(
    candidate: BindingCandidate,
    metrics: list[dict[str, Any]],
    dimensions: list[str] | None,
) -> float:
    """Bonus when candidate resource owns the requested fields."""
    needed = _fields_needed(metrics, dimensions)
    if not needed:
        return 0.0
    allowed = _resource_column_set(candidate.resource)
    if not allowed:
        return 0.0
    if needed <= allowed:
        return 3.0
    overlap = len(needed & allowed)
    if overlap == 0:
        return -4.0
    return -1.0 * (len(needed) - overlap)


def _metrics_wants_class_scale(metrics: list[dict[str, Any]]) -> bool:
    for m in metrics:
        op = (m.get("op") or "").lower()
        field = (m.get("field") or "").lower()
        if op == "count_distinct" and (
            field.lower() == "student_id" or "student" in field.lower()
        ):
            return True
    return False


def compatibility_score(
    candidate: BindingCandidate,
    *,
    metrics: list[dict[str, Any]],
    dimensions: list[str] | None,
    bind: BindMode,
    current_user_turn: int,
) -> float:
    score = 0.0
    rows = candidate.result_rows
    scanned = candidate.rows_scanned or 0
    wants_class = _metrics_wants_class_scale(metrics)

    if candidate.user_turn != current_user_turn:
        return -CROSS_TURN_PENALTY

    if bind is BindMode.CHAIN:
        if candidate.is_slice:
            score += 4.0
        else:
            score -= 2.0
        return score

    if bind is BindMode.FRESH:
        if candidate.is_broad_scan:
            score += 5.0
        elif not candidate.is_slice and rows > SLICE_MAX_ROWS:
            score += 3.0
        if candidate.is_slice:
            score -= 6.0
        if candidate.query_limit is not None:
            score -= 4.0
        return score

    # auto
    if wants_class or (not dimensions and rows <= SLICE_MAX_ROWS and scanned > rows * 2):
        if candidate.is_broad_scan:
            score += 4.0
        elif rows > SLICE_MAX_ROWS:
            score += 2.0
        if candidate.is_slice:
            score -= 5.0
        if candidate.query_limit is not None and scanned > max(rows, 1) * 10:
            score -= 3.0
    else:
        if candidate.is_slice:
            score += 2.0
        if candidate.is_broad_scan and not dimensions:
            score += 0.5

    if dimensions and candidate.is_broad_scan:
        score += 1.0

    score += _resource_field_compatibility(candidate, metrics, dimensions)

    return score


def pick_best_candidate(
    candidates: list[BindingCandidate],
    *,
    metrics: list[dict[str, Any]],
    dimensions: list[str] | None,
    bind: BindMode,
    current_user_turn: int,
) -> BindingCandidate | None:
    if not candidates:
        return None
    scored = [
        (
            compatibility_score(
                c,
                metrics=metrics,
                dimensions=dimensions,
                bind=bind,
                current_user_turn=current_user_turn,
            ),
            c,
        )
        for c in candidates
    ]
    scored.sort(key=lambda x: x[0], reverse=True)
    best_score, best = scored[0]
    if best_score <= -CROSS_TURN_PENALTY / 2:
        return None
    return best


def score_for_ref(
    candidate: BindingCandidate | None,
    *,
    metrics: list[dict[str, Any]],
    dimensions: list[str] | None,
    bind: BindMode,
    current_user_turn: int,
) -> float:
    if candidate is None:
        return -999.0
    return compatibility_score(
        candidate,
        metrics=metrics,
        dimensions=dimensions,
        bind=bind,
        current_user_turn=current_user_turn,
    )

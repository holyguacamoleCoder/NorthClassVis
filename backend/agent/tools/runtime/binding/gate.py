"""When aggregate binding must use semantic intent resolution."""

from __future__ import annotations

from dataclasses import dataclass, field

from .context import BindingContext, candidate_for_dataset_id
from .scoring import pick_best_candidate, score_for_ref
from .types import BindMode


@dataclass
class AmbiguityGateResult:
    triggered: bool
    reasons: list[str] = field(default_factory=list)


def _normalize_ref(ref: str) -> str:
    return ref.strip().replace("\\", "/")


def _has_slice_and_broad(ctx: BindingContext) -> bool:
    has_slice = any(c.is_slice for c in ctx.candidates)
    has_broad = any(c.is_broad_scan for c in ctx.candidates)
    return has_slice and has_broad


def check_ambiguity(ctx: BindingContext) -> AmbiguityGateResult:
    reasons: list[str] = []

    inp = ctx.model_input
    explicit_id = inp.get("dataset_id")
    explicit_ref = inp.get("result_ref")
    bind = BindMode.parse(ctx.model_bind)

    if explicit_id:
        cand = candidate_for_dataset_id(ctx, str(explicit_id))
        if cand and cand.user_turn != ctx.current_user_turn:
            reasons.append("CROSS_TURN_DATASET_ID")
        elif not cand:
            reasons.append("UNKNOWN_DATASET_ID")

    if explicit_ref and not explicit_id:
        norm = _normalize_ref(str(explicit_ref))
        in_turn = any(_normalize_ref(c.result_ref) == norm for c in ctx.candidates)
        if not in_turn:
            reasons.append("CROSS_TURN_REF")
        elif len(ctx.candidates) >= 2:
            explicit_cand = next(
                (c for c in ctx.candidates if _normalize_ref(c.result_ref) == norm),
                None,
            )
            best = pick_best_candidate(
                ctx.candidates,
                metrics=ctx.model_metrics,
                dimensions=ctx.model_dimensions,
                bind=bind,
                current_user_turn=ctx.current_user_turn,
            )
            if explicit_cand and best and explicit_cand.result_ref != best.result_ref:
                exp_s = score_for_ref(
                    explicit_cand,
                    metrics=ctx.model_metrics,
                    dimensions=ctx.model_dimensions,
                    bind=bind,
                    current_user_turn=ctx.current_user_turn,
                )
                best_s = score_for_ref(
                    best,
                    metrics=ctx.model_metrics,
                    dimensions=ctx.model_dimensions,
                    bind=bind,
                    current_user_turn=ctx.current_user_turn,
                )
                if best_s >= exp_s + 0.5:
                    reasons.append("EXPLICIT_REF_MISMATCH")

    if len(ctx.candidates) >= 2 and _has_slice_and_broad(ctx):
        reasons.append("MULTI_CANDIDATE_SLICE_BROAD")

    if len(ctx.candidates) >= 2 and not explicit_id:
        reasons.append("MULTI_CANDIDATE")

    if not ctx.teacher_message.strip() and len(ctx.candidates) >= 2:
        reasons.append("MISSING_TEACHER_MESSAGE")

    return AmbiguityGateResult(triggered=bool(reasons), reasons=reasons)


def should_skip_resolver(ctx: BindingContext, gate: AmbiguityGateResult) -> bool:
    """Single unambiguous candidate with matching explicit dataset_id."""
    if gate.triggered:
        return False
    if len(ctx.candidates) != 1:
        return False
    explicit_id = ctx.model_input.get("dataset_id")
    if explicit_id and str(explicit_id) == ctx.candidates[0].dataset_id:
        return True
    if not ctx.model_input.get("result_ref"):
        return True
    norm = _normalize_ref(str(ctx.model_input["result_ref"]))
    return _normalize_ref(ctx.candidates[0].result_ref) == norm

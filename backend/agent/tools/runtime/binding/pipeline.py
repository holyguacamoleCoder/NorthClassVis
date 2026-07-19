"""Orchestrate semantic + rule-based aggregate input binding."""

from __future__ import annotations

from typing import Any

from data.dataset_registry import (
    find_dataset_by_ref,
    format_catalog_hint,
    get_dataset_record,
    resolve_dataset_id,
)

from loop_state import AnalysisToolContext, QuerySnapshot

from ..data.types import AggregateBinding
from .context import build_binding_context, candidate_for_dataset_id
from .gate import check_ambiguity
from .intent import resolve_binding_intent
from .rules import (
    cross_turn_reject_message,
    missing_turn_query_message,
    should_reject_silent_cross_turn,
    teacher_wants_chain_slice,
    teacher_wants_class_wide_over_slice,
    try_rule_chain_slice,
    try_rule_fresh_broad,
)
from .scoring import pick_best_candidate
from .types import BindMode, DatasetBindingDecision
from .validate import validate_decision


def _finalize_binding(
    ctx,
    *,
    dataset_id: str | None,
    result_ref: str | None,
    decision: str,
    trace: dict[str, Any],
    scope: str = "explicit_dataset",
    corrected: bool = False,
    corrected_from: str | None = None,
    auto_input: bool = False,
) -> AggregateBinding:
    """Run column/lineage validate before accepting any successful bind."""
    if not dataset_id or not result_ref:
        hint = format_catalog_hint(ctx.session_id)
        return AggregateBinding(
            error=(
                "Error: 无法确定 aggregate 绑定的 dataset_id/result_ref。"
                "请 list_datasets 后显式传入 input.dataset_id。"
                + (f"\n{hint}" if hint else "")
            ),
            trace={**trace, "resolver": decision},
        )
    dec = DatasetBindingDecision(
        scope=scope,
        dataset_id=str(dataset_id),
        result_ref=str(result_ref),
        rationale=decision,
        resolver=decision,
        overrides_model_ref=corrected,
    )
    err = validate_decision(dec, ctx)
    if err:
        hint = format_catalog_hint(ctx.session_id)
        return AggregateBinding(
            error=err + (f"\n{hint}" if hint else ""),
            trace={**trace, "resolver": decision, "validate_failed": True},
        )
    return AggregateBinding(
        result_ref=dec.result_ref,
        dataset_id=dec.dataset_id,
        decision=decision,
        corrected=corrected,
        corrected_from=corrected_from,
        auto_input=auto_input,
        trace={**trace, "resolver": decision, "bound_result_ref": dec.result_ref, "bound_dataset_id": dec.dataset_id},
    )


def resolve_aggregate_binding(
    inp: dict[str, Any],
    *,
    metrics: list[dict[str, Any]],
    dimensions: list[str] | None,
    bind: BindMode,
    analysis_context: AnalysisToolContext | None,
    batch_snapshots: list[QuerySnapshot],
    llm_client: Any | None = None,
) -> AggregateBinding:
    ctx = build_binding_context(
        inp=inp,
        metrics=metrics,
        dimensions=dimensions,
        bind=bind.value if isinstance(bind, BindMode) else str(bind),
        analysis_context=analysis_context,
        batch_snapshots=batch_snapshots,
    )
    session_id = ctx.session_id
    gate = check_ambiguity(ctx)
    trace: dict[str, Any] = {
        "gate_triggered": gate.triggered,
        "gate_reasons": gate.reasons,
        "candidate_count": len(ctx.candidates),
        "teacher_message_preview": (ctx.teacher_message or "")[:200],
    }

    chain_id = inp.get("chain_from_dataset_id")
    if chain_id:
        rec = get_dataset_record(session_id, str(chain_id))
        if not rec:
            hint = format_catalog_hint(session_id)
            return AggregateBinding(
                error=(
                    f"Error: 未知 chain_from_dataset_id={chain_id!r}。"
                    + (f"\n{hint}" if hint else "")
                ),
                trace=trace,
            )
        dec = DatasetBindingDecision(
            scope="chain_explicit",
            dataset_id=rec.dataset_id,
            result_ref=rec.result_ref,
            rationale="显式 chain_from_dataset_id",
            resolver="explicit",
        )
        err = validate_decision(dec, ctx)
        if err:
            return AggregateBinding(error=err, trace=trace)
        trace["resolver"] = "chain_explicit"
        return AggregateBinding(
            result_ref=dec.result_ref,
            dataset_id=dec.dataset_id,
            decision="chain_explicit",
            trace=trace,
        )

    def _norm_ref(ref: str) -> str:
        return ref.strip().replace("\\", "/")

    explicit_id = inp.get("dataset_id")
    if explicit_id:
        cand = candidate_for_dataset_id(ctx, str(explicit_id))
        if not cand:
            hint = format_catalog_hint(session_id)
            return AggregateBinding(
                error=f"Error: 未知 dataset_id={explicit_id!r}。" + (f"\n{hint}" if hint else ""),
                trace=trace,
            )
        dec = DatasetBindingDecision(
            scope="prior_turn_dataset" if cand.user_turn != ctx.current_user_turn else "explicit_dataset",
            dataset_id=cand.dataset_id or str(explicit_id),
            result_ref=cand.result_ref,
            rationale="显式 dataset_id",
            resolver="explicit",
        )
        err = validate_decision(dec, ctx)
        if err:
            return AggregateBinding(error=err, trace=trace)
        if (
            teacher_wants_chain_slice(ctx.teacher_message)
            and not teacher_wants_class_wide_over_slice(ctx.teacher_message)
            and not cand.is_slice
        ):
            hint = format_catalog_hint(session_id)
            return AggregateBinding(
                error=(
                    f"Error: dataset_id={explicit_id!r} 为全量（{cand.result_rows} 行），"
                    "但教师话要求切片/「这些记录」口径。请 list_datasets 后改选 limit 切片 dataset_id。"
                    + (f"\n{hint}" if hint else "")
                ),
                trace={**trace, "resolver": "explicit_dataset_id"},
            )
        trace["resolver"] = "explicit_dataset_id"
        trace["bound_result_ref"] = dec.result_ref
        trace["bound_dataset_id"] = dec.dataset_id
        return AggregateBinding(
            result_ref=dec.result_ref,
            dataset_id=dec.dataset_id,
            decision=dec.scope,
            trace=trace,
        )

    given_ref = inp.get("result_ref")
    if given_ref:
        norm_given = _norm_ref(str(given_ref))
        in_turn = any(_norm_ref(c.result_ref) == norm_given for c in ctx.candidates)
        if not in_turn:
            rec = find_dataset_by_ref(session_id, str(given_ref))
            if rec and rec.user_turn != ctx.current_user_turn:
                hint = format_catalog_hint(session_id)
                return AggregateBinding(
                    error=(
                        "Error: result_ref 来自上一轮提问，不能自动续用。"
                        "请 list_datasets，再在 input.dataset_id 中显式引用；"
                        "仅当班级/周次/过滤条件变化时才重新 query_data。"
                        + (f"\n{hint}" if hint else "")
                    ),
                    trace=trace,
                )
            best = pick_best_candidate(
                ctx.candidates,
                metrics=metrics,
                dimensions=dimensions,
                bind=bind,
                current_user_turn=ctx.current_user_turn,
            )
            if best and bind is not BindMode.FRESH:
                return _finalize_binding(
                    ctx,
                    dataset_id=best.dataset_id,
                    result_ref=best.result_ref,
                    decision="turn_mismatch",
                    trace=trace,
                    corrected=True,
                    corrected_from=str(given_ref),
                )

    bind_value = bind.value if isinstance(bind, BindMode) else str(bind)
    rule_broad = try_rule_fresh_broad(ctx, inp, trace, bind=bind_value)
    if rule_broad is not None:
        return rule_broad

    rule_slice = try_rule_chain_slice(ctx, inp, trace)
    if rule_slice is not None:
        return rule_slice

    if should_reject_silent_cross_turn(ctx, inp):
        return AggregateBinding(
            error=missing_turn_query_message(session_id),
            trace={**trace, "resolver": "silent_cross_turn_reject"},
        )

    if not gate.triggered and len(ctx.candidates) == 1:
        c = ctx.candidates[0]
        given_ref = inp.get("result_ref")
        corrected = False
        corrected_from = None
        if given_ref and given_ref.strip().replace("\\", "/") != c.result_ref.strip().replace(
            "\\", "/"
        ):
            corrected = True
            corrected_from = str(given_ref)
        return _finalize_binding(
            ctx,
            dataset_id=c.dataset_id,
            result_ref=c.result_ref,
            decision="single_candidate",
            trace=trace,
            corrected=corrected,
            corrected_from=corrected_from,
            auto_input=not bool(given_ref),
        )

    if not gate.triggered and not inp.get("result_ref") and not inp.get("dataset_id"):
        best = pick_best_candidate(
            ctx.candidates,
            metrics=metrics,
            dimensions=dimensions,
            bind=bind,
            current_user_turn=ctx.current_user_turn,
        )
        if best:
            return _finalize_binding(
                ctx,
                dataset_id=best.dataset_id,
                result_ref=best.result_ref,
                decision="rule_pick_best",
                trace=trace,
                scope=bind.value if isinstance(bind, BindMode) else str(bind) or "explicit_dataset",
                auto_input=True,
            )

    if "CROSS_TURN_REF" in gate.reasons and not explicit_id:
        return AggregateBinding(
            error=cross_turn_reject_message(session_id),
            trace={**trace, "resolver": "cross_turn_ref_reject"},
        )

    if gate.triggered or len(ctx.candidates) >= 2 or (
        inp.get("result_ref") and len(ctx.candidates) >= 1
    ):
        decision = resolve_binding_intent(ctx, llm_client)
        trace["resolver"] = decision.resolver if decision else None
        trace["gate_reasons"] = gate.reasons
        if decision:
            err = validate_decision(decision, ctx)
            if err:
                hint = format_catalog_hint(session_id)
                return AggregateBinding(
                    error=err + (f"\n{hint}" if hint else ""),
                    trace=trace,
                )
            model_ref = inp.get("result_ref")
            corrected_from = str(model_ref) if model_ref else None
            return AggregateBinding(
                result_ref=decision.result_ref,
                dataset_id=decision.dataset_id,
                decision=f"{decision.scope}:{decision.resolver}",
                corrected=decision.overrides_model_ref,
                corrected_from=corrected_from if decision.overrides_model_ref else None,
                auto_input=not bool(inp.get("result_ref")),
                trace={
                    **trace,
                    "rationale": decision.rationale,
                    "scope": decision.scope,
                    "confidence": decision.confidence,
                },
            )

        if "CROSS_TURN_REF" in gate.reasons:
            hint = format_catalog_hint(session_id)
            return AggregateBinding(
                error=(
                    "Error: result_ref 来自上一轮提问，不能自动续用。"
                    "请 list_datasets，再传 input.dataset_id；"
                    "仅当口径变化时才重新 query_data。"
                    + (f"\n{hint}" if hint else "")
                ),
                trace=trace,
            )
        hint = format_catalog_hint(session_id)
        return AggregateBinding(
            error=(
                "Error: 无法解析 aggregate 应绑定的数据集（语义 resolver 未决）。"
                "请 list_datasets 后使用 input.dataset_id；"
                "仅当本回合尚无合适数据集且口径变化时再 query_data。"
                + (f"\n{hint}" if hint else "")
            ),
            trace=trace,
        )

    if inp.get("dataset_id"):
        ref = resolve_dataset_id(session_id, str(inp["dataset_id"]))
        if ref:
            return _finalize_binding(
                ctx,
                dataset_id=str(inp["dataset_id"]),
                result_ref=ref,
                decision="dataset_id_fallback",
                trace=trace,
            )

    hint = format_catalog_hint(session_id)
    return AggregateBinding(
        error=(
            "Error: aggregate_data 缺少可用的本回合 query 结果。"
            "优先：list_datasets → input.dataset_id；"
            "仅当会话中还没有匹配口径的数据时再 query_data（省略 limit 做全量）。"
            "列名不确定时先 inspect_schema。"
            + (f"\n{hint}" if hint else "")
        ),
        trace=trace,
    )

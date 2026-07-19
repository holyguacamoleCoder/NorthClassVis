"""Hard binding rules applied before LLM intent resolution."""

from __future__ import annotations

import re
from typing import Any

from ..data.types import AggregateBinding
from .context import BindingContext, candidate_for_dataset_id
from .types import DatasetBindingDecision

_CHAIN_RE = re.compile(
    r"这些|这批|上述|刚查|这份|汇总这|记录的分|最低\s*\d+|前\s*\d+\s*条|\d+\s*条",
    re.IGNORECASE,
)
_CLASS_WIDE_RE = re.compile(
    r"全班|整体|规模|偏科|概况|大致水平|整体情况|知识点|全班同学|全班口径|全量",
    re.IGNORECASE,
)
# 全班口径显式优先于「这 N 条」等切片指代（如「全班口径，不是这10条」）
_CLASS_WIDE_PRIORITY_RE = re.compile(
    r"全班口径|不是这|而非这|不是\s*\d+\s*条|全班.*(不是|而非)",
    re.IGNORECASE,
)
_SLICE_MAX_ROWS = 50


def teacher_wants_chain_slice(message: str) -> bool:
    return bool(_CHAIN_RE.search(message or ""))


def teacher_wants_class_wide(message: str) -> bool:
    return bool(_CLASS_WIDE_RE.search(message or ""))


def teacher_wants_class_wide_over_slice(message: str) -> bool:
    """Teacher explicitly asks for class-wide scope over chain/slice wording."""
    return bool(_CLASS_WIDE_PRIORITY_RE.search(message or ""))


def current_turn_candidates(ctx: BindingContext) -> list:
    turn = ctx.current_user_turn
    return [c for c in ctx.candidates if c.user_turn == turn]


def _norm_ref(ref: str) -> str:
    return ref.strip().replace("\\", "/")


def cross_turn_reject_message(session_id: str | None) -> str:
    from data.dataset_registry import format_catalog_hint

    hint = format_catalog_hint(session_id)
    base = (
        "Error: result_ref 来自上一轮提问，不能自动续用。"
        "请先 list_datasets，再在 aggregate_data 的 input.dataset_id 中显式引用本会话已有数据集。"
        "仅当口径确实变化（班级/周次/过滤条件不同）时才重新 query_data。"
    )
    return base + (f"\n{hint}" if hint else "")


def missing_turn_query_message(session_id: str | None) -> str:
    from data.dataset_registry import format_catalog_hint

    hint = format_catalog_hint(session_id)
    base = (
        "Error: 本回合尚无可用的 query 工作集，且禁止静默绑定上一轮 result_ref。"
        "跨轮续算：list_datasets → aggregate_data(input.dataset_id=…)。"
        "仅当教师要求新口径（不同班级/周次/条件）时才 query_data。"
    )
    return base + (f"\n{hint}" if hint else "")


def should_reject_silent_cross_turn(ctx: BindingContext, inp: dict[str, Any]) -> bool:
    """Cross-turn: new user turn with no in-turn queries and no explicit dataset_id."""
    if inp.get("dataset_id") or inp.get("chain_from_dataset_id"):
        return False
    if ctx.current_user_turn <= 1:
        return False
    return len(current_turn_candidates(ctx)) == 0


def try_rule_fresh_broad(
    ctx: BindingContext,
    inp: dict[str, Any],
    trace: dict[str, Any],
    *,
    bind: str,
) -> AggregateBinding | None:
    """bind=fresh + 全班口径 → 强制本回合 broad（非切片）。"""
    if bind != "fresh":
        return None
    if not teacher_wants_class_wide(ctx.teacher_message):
        return None

    cands = current_turn_candidates(ctx)
    broads = [c for c in cands if c.query_limit is None and c.result_rows > _SLICE_MAX_ROWS]
    if not broads:
        broads = [c for c in cands if not c.is_slice]
    if not broads:
        return None

    pick = max(broads, key=lambda c: c.result_rows)
    if not pick.dataset_id:
        return None

    decision = DatasetBindingDecision(
        scope="class_wide",
        dataset_id=pick.dataset_id,
        result_ref=pick.result_ref,
        confidence="high",
        rationale="规则：bind=fresh 且教师话含全班口径，绑定本回合 broad。",
        resolver="rule_fresh_broad",
    )
    from .validate import validate_decision

    err = validate_decision(decision, ctx)
    if err:
        return AggregateBinding(error=err, trace={**trace, "resolver": "rule_fresh_broad"})

    trace["resolver"] = "rule_fresh_broad"
    trace["bound_result_ref"] = pick.result_ref
    trace["bound_dataset_id"] = pick.dataset_id
    return AggregateBinding(
        result_ref=pick.result_ref,
        dataset_id=pick.dataset_id,
        decision="class_wide:rule",
        auto_input=not bool(inp.get("result_ref")),
        trace={**trace, "scope": "class_wide"},
    )


def try_rule_chain_slice(
    ctx: BindingContext,
    inp: dict[str, Any],
    trace: dict[str, Any],
) -> AggregateBinding | None:
    """Force slice binding when teacher refers to 「这些 / 最低 N 条」."""
    if not teacher_wants_chain_slice(ctx.teacher_message):
        return None
    if teacher_wants_class_wide_over_slice(ctx.teacher_message):
        return None
    if teacher_wants_class_wide(ctx.teacher_message) and not teacher_wants_chain_slice(
        ctx.teacher_message
    ):
        return None

    slices = [c for c in current_turn_candidates(ctx) if c.is_slice]
    if not slices:
        return None

    pick = slices[-1]
    if not pick.dataset_id:
        return None

    model_ref = inp.get("result_ref")
    corrected = False
    corrected_from: str | None = None
    if model_ref and _norm_ref(str(model_ref)) != _norm_ref(pick.result_ref):
        corrected = True
        corrected_from = str(model_ref)

    decision = DatasetBindingDecision(
        scope="chain_slice",
        dataset_id=pick.dataset_id,
        result_ref=pick.result_ref,
        confidence="high",
        rationale="规则：教师话含切片指代（这些/最低N条），绑定本回合 slice。",
        overrides_model_ref=corrected,
        resolver="rule_chain_slice",
    )
    from .validate import validate_decision

    err = validate_decision(decision, ctx)
    if err:
        return AggregateBinding(error=err, trace={**trace, "resolver": "rule_chain_slice"})

    trace["resolver"] = "rule_chain_slice"
    trace["bound_result_ref"] = pick.result_ref
    trace["bound_dataset_id"] = pick.dataset_id
    return AggregateBinding(
        result_ref=pick.result_ref,
        dataset_id=pick.dataset_id,
        decision="chain_slice:rule",
        corrected=corrected,
        corrected_from=corrected_from,
        auto_input=not bool(model_ref),
        trace={**trace, "scope": "chain_slice"},
    )

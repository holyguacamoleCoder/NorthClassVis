"""Hard validation after semantic binding decision."""

from __future__ import annotations

from .context import BindingContext, candidate_for_dataset_id, catalog_item
from .rules import teacher_wants_class_wide
from .types import DatasetBindingDecision


def validate_decision(
    decision: DatasetBindingDecision,
    ctx: BindingContext,
) -> str | None:
    cand = candidate_for_dataset_id(ctx, decision.dataset_id)
    if not cand:
        return f"Error: dataset_id {decision.dataset_id!r} 不在本会话 catalog 中。"

    item = catalog_item(ctx, decision.dataset_id)
    scope = decision.scope

    if scope == "chain_slice":
        if not cand.is_slice:
            return (
                f"Error: 绑定 scope=chain_slice 但 {decision.dataset_id} 有 "
                f"{cand.result_rows} 行（非切片）。请 list_datasets 后重选，或先 limit query。"
            )
    elif scope == "class_wide":
        if (
            cand.user_turn < ctx.current_user_turn
            and not teacher_wants_class_wide(ctx.teacher_message)
        ):
            return (
                f"Error: 绑定 scope=class_wide 但 {decision.dataset_id} 来自"
                f" user_turn={cand.user_turn}（当前 turn={ctx.current_user_turn}），"
                "且教师话未要求全班/整体口径。"
                "跨轮请传 input.dataset_id，或先对本题 query_data（省略 limit）。"
            )
        if cand.is_slice and not cand.is_broad_scan:
            return (
                f"Error: 绑定 scope=class_wide 但 {decision.dataset_id} 仅为 "
                f"{cand.result_rows} 行"
                f"{f'（limit={cand.query_limit}）' if cand.query_limit else ''}。"
                "全班统计请先 query_data（省略 limit）再 aggregate。"
            )
    elif scope == "prior_turn_dataset":
        if cand.user_turn == ctx.current_user_turn and len(ctx.candidates) > 1:
            pass
        elif cand.user_turn != ctx.current_user_turn:
            pass
    elif scope == "explicit_dataset":
        pass

    if item and scope == "class_wide" and item.get("query_limit"):
        return (
            f"Error: {decision.dataset_id} 带 query_limit，不能用于全班口径。"
            "请对新题执行无 limit 的 query_data。"
        )

    decision.result_ref = cand.result_ref
    return None

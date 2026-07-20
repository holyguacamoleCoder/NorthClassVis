"""Per-turn agent hints merged into the current user message (prefix-cache safe).

Volatile session state that used to live in the system prompt is assembled here
and composed only into the *new* user turn — never rewritten into older messages.
"""

from __future__ import annotations

from typing import Any

from common.prompts import (
    format_datasets_catalog_section,
    format_run_modify_section,
    format_session_plan_section,
)
from data.filter_context import FilterContext
from hints.report_continue import (
    format_report_continue_hint,
    should_attach_report_continue_hint,
)
from session.ui_scope import format_turn_scope_hint


def build_turn_agent_hint(
    *,
    ui_scope: dict[str, Any] | None = None,
    filter_context: FilterContext | None = None,
    modify_context: dict[str, Any] | None = None,
    todo_items: list[dict[str, str]] | None = None,
    report_continue_path: str | None = None,
    datasets_catalog_text: str | None = None,
    teacher_message: str | None = None,
) -> str | None:
    """Join scope / modify / todo / reminder / optional catalog into one turn hint."""
    blocks: list[str] = []

    scope = format_turn_scope_hint(ui_scope=ui_scope, filter_context=filter_context)
    if scope:
        blocks.append(scope.strip())

    modify_block = format_run_modify_section(modify_context)
    if modify_block:
        blocks.append(modify_block.strip())

    plan_block = format_session_plan_section(todo_items or [])
    if plan_block:
        blocks.append(plan_block.strip())

    if datasets_catalog_text and str(datasets_catalog_text).strip():
        catalog = format_datasets_catalog_section(str(datasets_catalog_text).strip())
        if catalog:
            blocks.append(catalog.strip())

    if report_continue_path and should_attach_report_continue_hint(teacher_message):
        blocks.append(format_report_continue_hint(report_continue_path).strip())

    if not blocks:
        return None
    return "\n\n".join(blocks)


def optional_session_catalog_for_turn(
    session_id: str | None,
    *,
    messages_before_turn: list[dict[str, Any]] | None = None,
    tail: int = 8,
) -> str | None:
    """First-user-turn catalog snapshot (strategy A once); later turns rely on tool results."""
    if not session_id:
        return None
    prior_users = 0
    for msg in messages_before_turn or []:
        if isinstance(msg, dict) and msg.get("role") == "user":
            prior_users += 1
    if prior_users > 0:
        return None
    from data.dataset_registry import format_prompt_catalog

    text = (format_prompt_catalog(session_id, tail=tail) or "").strip()
    return text or None

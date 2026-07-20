"""Replace older tool result bodies with a short placeholder (cache-aware)."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from common.logger import get_logger, log_event
from skills.message_meta import is_pinned_message

from .config import ContextCompactConfig, DEFAULT_CONFIG
from .persist import COMPACTED_TOOL_PLACEHOLDER
from .tool_result_summary import extract_tabular_summary

_log = get_logger("context.micro")

# Tool results kept verbatim in message history (fallback when _agent_meta absent).
_PINNED_TOOL_NAMES = frozenset({"load_skill", "load_reference", "todo_write"})


def _tool_names_by_call_id(messages: list[dict[str, Any]]) -> dict[str, str]:
    names: dict[str, str] = {}
    for msg in messages:
        if msg.get("role") != "assistant":
            continue
        for call in msg.get("tool_calls") or []:
            call_id = call.get("id")
            if not call_id:
                continue
            fn = call.get("function") or {}
            tool_name = call.get("name") or fn.get("name") or ""
            if tool_name:
                names[str(call_id)] = str(tool_name)
    return names


def collect_tool_message_indices(messages: list[dict[str, Any]]) -> list[int]:
    return [i for i, msg in enumerate(messages) if msg.get("role") == "tool"]


def compact_tool_content(content: str) -> str:
    """Replace body with placeholder but keep a one-line data-tool summary if present."""
    summary = extract_tabular_summary(content)
    if summary:
        return f"{COMPACTED_TOOL_PLACEHOLDER}\n{summary}"
    return COMPACTED_TOOL_PLACEHOLDER


def _should_skip_micro_compact(msg: dict[str, Any], tool_names: dict[str, str]) -> bool:
    if is_pinned_message(msg):
        return True
    call_id = str(msg.get("tool_call_id") or "")
    return tool_names.get(call_id) in _PINNED_TOOL_NAMES


def micro_compact_messages(
    messages: list[dict[str, Any]],
    *,
    config: ContextCompactConfig = DEFAULT_CONFIG,
    protect_prefix_count: int | None = None,
    on_cache_bust: Callable[[str], None] | None = None,
) -> int:
    """Replace older tool result bodies with a short placeholder.

    When ``protect_prefix_count`` is set, prefer compacting only messages at
    index >= that count (tail not yet in the prior LLM request prefix). If
    protected messages must still be compacted to free space, emit
    ``cache_bust_reason=micro_compact``.
    """
    if not config.enabled:
        return 0

    tool_indices = collect_tool_message_indices(messages)
    if len(tool_indices) <= config.keep_recent_tool_results:
        return 0

    to_compact = tool_indices[: -config.keep_recent_tool_results]
    tool_names = _tool_names_by_call_id(messages)
    compacted = 0
    skipped_protected = 0
    for index in to_compact:
        if protect_prefix_count is not None and index < protect_prefix_count:
            # Leave cached prefix untouched; macro-compact frees space if needed.
            skipped_protected += 1
            continue
        msg = messages[index]
        if _should_skip_micro_compact(msg, tool_names):
            continue
        content = msg.get("content", "")
        if not isinstance(content, str):
            continue
        if len(content) <= config.micro_compact_min_chars:
            continue
        if content.startswith(COMPACTED_TOOL_PLACEHOLDER):
            continue
        msg["content"] = compact_tool_content(content)
        compacted += 1

    if skipped_protected and protect_prefix_count is not None:
        log_event(
            _log,
            logging.DEBUG,
            "micro_compact_skip_protected",
            skipped=skipped_protected,
            protect_prefix_count=protect_prefix_count,
        )

    if compacted:
        log_event(
            _log,
            logging.INFO,
            "micro_compact",
            compacted=compacted,
            kept_recent=config.keep_recent_tool_results,
            protect_prefix_count=protect_prefix_count,
            skipped_protected=skipped_protected,
        )
    return compacted

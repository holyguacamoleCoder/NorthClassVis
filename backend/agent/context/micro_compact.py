import logging
from typing import Any

from common.logger import get_logger, log_event

from .config import ContextCompactConfig, DEFAULT_CONFIG
from .persist import COMPACTED_TOOL_PLACEHOLDER
from .tool_result_summary import extract_tabular_summary

_log = get_logger("context.micro")


def collect_tool_message_indices(messages: list[dict[str, Any]]) -> list[int]:
    return [i for i, msg in enumerate(messages) if msg.get("role") == "tool"]


def compact_tool_content(content: str) -> str:
    """Replace body with placeholder but keep a one-line data-tool summary if present."""
    summary = extract_tabular_summary(content)
    if summary:
        return f"{COMPACTED_TOOL_PLACEHOLDER}\n{summary}"
    return COMPACTED_TOOL_PLACEHOLDER


def micro_compact_messages(
    messages: list[dict[str, Any]],
    *,
    config: ContextCompactConfig = DEFAULT_CONFIG,
) -> int:
    """Replace older tool result bodies with a short placeholder. Returns count compacted."""
    if not config.enabled:
        return 0

    tool_indices = collect_tool_message_indices(messages)
    if len(tool_indices) <= config.keep_recent_tool_results:
        return 0

    to_compact = tool_indices[: -config.keep_recent_tool_results]
    compacted = 0
    for index in to_compact:
        msg = messages[index]
        content = msg.get("content", "")
        if not isinstance(content, str):
            continue
        if len(content) <= config.micro_compact_min_chars:
            continue
        if content.startswith(COMPACTED_TOOL_PLACEHOLDER):
            continue
        msg["content"] = compact_tool_content(content)
        compacted += 1

    if compacted:
        log_event(
            _log,
            logging.INFO,
            "micro_compact",
            compacted=compacted,
            kept_recent=config.keep_recent_tool_results,
        )
    return compacted

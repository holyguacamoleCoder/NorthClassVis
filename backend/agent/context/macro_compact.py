import json
import logging
import time
from typing import Any

from common.llm_client import LLMClient
from common.logger import get_logger, log_event
from common.prompts import (
    COMPACT_SUMMARY_FALLBACK,
    COMPACT_SUMMARY_SYSTEM,
    format_compact_summary_user,
    format_compact_user_message,
)
from skills.message_meta import is_pinned_message

from .config import ContextCompactConfig, DEFAULT_CONFIG
from .estimate import estimate_context_size
from .state import CompactState

_log = get_logger("context.macro")

# Backward-compatible aliases for tests or external imports
SUMMARY_SYSTEM = COMPACT_SUMMARY_SYSTEM


def write_transcript(
    messages: list[dict[str, Any]],
    *,
    config: ContextCompactConfig = DEFAULT_CONFIG,
) -> str:
    # 将整个message写入文件
    config.transcript_dir.mkdir(parents=True, exist_ok=True)
    path = config.transcript_dir / f"transcript_{int(time.time())}.jsonl"
    with path.open("w", encoding="utf-8") as handle:
        for message in messages:
            handle.write(json.dumps(message, default=str, ensure_ascii=False) + "\n")
    return str(path)


def extract_pinned_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Tool messages marked pin; preserved across macro compact."""
    return [dict(m) for m in messages if m.get("role") == "tool" and is_pinned_message(m)]


def _tail_indices(
    messages: list[dict[str, Any]],
    *,
    config: ContextCompactConfig,
) -> set[int]:
    if config.keep_tail_turns <= 0 or not messages:
        return set()
    indices: set[int] = set()
    i = len(messages) - 1
    while i >= 0 and messages[i].get("role") == "tool":
        if is_pinned_message(messages[i]):
            i -= 1
            continue
        indices.add(i)
        i -= 1
    if i >= 0 and messages[i].get("role") == "assistant" and messages[i].get("tool_calls"):
        indices.add(i)
    return indices


def _messages_for_summary(
    messages: list[dict[str, Any]],
    *,
    config: ContextCompactConfig,
) -> list[dict[str, Any]]:
    skip = _tail_indices(messages, config=config)
    for i, msg in enumerate(messages):
        if msg.get("role") == "tool" and is_pinned_message(msg):
            skip.add(i)
    return [m for i, m in enumerate(messages) if i not in skip]


def summarize_history(
    messages: list[dict[str, Any]],
    llm_client: LLMClient,
    *,
    config: ContextCompactConfig = DEFAULT_CONFIG,
) -> str:
    # 压缩：调用llm总结历史
    conversation = json.dumps(messages, default=str, ensure_ascii=False)[: config.summary_input_chars]
    prompt = format_compact_summary_user(conversation)
    summary = llm_client.chat_text(
        system_prompt=COMPACT_SUMMARY_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=config.summary_max_tokens,
        langfuse_name="macro_compact",
        langfuse_metadata={"purpose": "macro_compact"},
    )
    return (summary or "").strip() or COMPACT_SUMMARY_FALLBACK


def extract_tail_messages(
    messages: list[dict[str, Any]],
    *,
    config: ContextCompactConfig = DEFAULT_CONFIG,
) -> list[dict[str, Any]]:
    # 保留最后一批工具调用的消息，后续会拼接在summary之后
    if config.keep_tail_turns <= 0 or not messages:
        return []

    tail: list[dict[str, Any]] = []
    i = len(messages) - 1
    while i >= 0 and messages[i].get("role") == "tool":
        if is_pinned_message(messages[i]):
            i -= 1
            continue
        tail.insert(0, messages[i])
        i -= 1

    if i >= 0 and messages[i].get("role") == "assistant" and messages[i].get("tool_calls"):
        tail.insert(0, messages[i])
    return tail


def build_compacted_messages(
    summary: str,
    *,
    focus: str | None = None,
    compact_state: CompactState | None = None,
    pinned: list[dict[str, Any]] | None = None,
    tail: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    from skills.message_meta import attach_ui_hidden_meta
    from skills.tool_result import CONTENT_KIND_COMPACT_SUMMARY

    recent = list(compact_state.recent_files) if compact_state and compact_state.recent_files else None
    summary_msg = attach_ui_hidden_meta(
        {
            "role": "user",
            "content": format_compact_user_message(
                summary,
                focus=focus,
                recent_files=recent,
            ),
        },
        content_kind=CONTENT_KIND_COMPACT_SUMMARY,
    )
    compacted = [summary_msg]
    if pinned:
        compacted.extend(pinned)
    if tail:
        compacted.extend(tail)
    return compacted


def compact_history(
    messages: list[dict[str, Any]],
    llm_client: LLMClient,
    compact_state: CompactState,
    *,
    focus: str | None = None,
    config: ContextCompactConfig = DEFAULT_CONFIG,
    reason: str = "auto",
) -> list[dict[str, Any]]:
    # 压缩：调用llm总结历史，并构建压缩后的消息
    size_before = estimate_context_size(messages)
    transcript_path = write_transcript(messages, config=config)
    pinned = extract_pinned_messages(messages)
    tail = extract_tail_messages(messages, config=config)
    to_summarize = _messages_for_summary(messages, config=config)
    summary = summarize_history(to_summarize, llm_client, config=config)
    compact_state.has_compacted = True
    compact_state.last_summary = summary
    new_messages = build_compacted_messages(
        summary,
        focus=focus,
        compact_state=compact_state,
        pinned=pinned,
        tail=tail,
    )
    size_after = estimate_context_size(new_messages)
    log_event(
        _log,
        logging.INFO,
        "macro_compact",
        reason=reason,
        transcript_path=transcript_path,
        size_before=size_before,
        size_after=size_after,
        tail_messages=len(tail),
        pinned_messages=len(pinned),
    )
    return new_messages

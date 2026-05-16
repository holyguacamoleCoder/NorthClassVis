import json
import logging
import time
from typing import Any

from common.llm_client import LLMClient
from common.logger import get_logger, log_event

from .config import ContextCompactConfig, DEFAULT_CONFIG
from .estimate import estimate_context_size
from .state import CompactState

_log = get_logger("context.macro")

SUMMARY_SYSTEM = (
    "You summarize coding-agent conversations so work can continue in a smaller context. "
    "Be compact but concrete."
)

SUMMARY_USER_TEMPLATE = """Summarize this teaching-data-analysis-agent conversation so work can continue.
Preserve:
1. The current goal
2. Important findings and decisions
3. Files read or changed
4. Remaining work
5. User constraints and preferences

Conversation (JSON):
{conversation}
"""


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


def summarize_history(
    messages: list[dict[str, Any]],
    llm_client: LLMClient,
    *,
    config: ContextCompactConfig = DEFAULT_CONFIG,
) -> str:
    # 压缩：调用llm总结历史
    conversation = json.dumps(messages, default=str, ensure_ascii=False)[: config.summary_input_chars]
    prompt = SUMMARY_USER_TEMPLATE.format(conversation=conversation)
    summary = llm_client.chat_text(
        system_prompt=SUMMARY_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=config.summary_max_tokens,
    )
    return (summary or "").strip() or "(Summary unavailable; continue from recent tool results.)"


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
    tail: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    # 构建压缩后的消息
    body = summary
    if focus:
        body += f"\n\nFocus to preserve next: {focus}"
    if compact_state and compact_state.recent_files:
        recent_lines = "\n".join(f"- {path}" for path in compact_state.recent_files)
        body += f"\n\nRecent files to reopen if needed:\n{recent_lines}"

    compacted = [
        {
            "role": "user",
            "content": (
                "This conversation was compacted so the agent can continue working.\n\n"
                f"{body}"
            ),
        }
    ]
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
    tail = extract_tail_messages(messages, config=config)
    summary = summarize_history(messages, llm_client, config=config)
    compact_state.has_compacted = True
    compact_state.last_summary = summary
    new_messages = build_compacted_messages(
        summary,
        focus=focus,
        compact_state=compact_state,
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
    )
    return new_messages

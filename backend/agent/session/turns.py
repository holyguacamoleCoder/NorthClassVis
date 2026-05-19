"""User-turn counting for loop logging across restarts."""

from __future__ import annotations

from typing import Any


def count_user_turns(messages: list[dict[str, Any]]) -> int:
    return sum(1 for message in messages if message.get("role") == "user")


def resolve_loop_turn_count(
    messages: list[dict[str, Any]],
    *,
    stored_user_turn_count: int = 0,
) -> int:
    """
    Turn number for the next loop_begin log line.

    Prefer live user messages; fall back to stored high-water mark after compaction.
    """
    from_messages = count_user_turns(messages)
    if from_messages > 0:
        return max(from_messages, stored_user_turn_count)
    return max(stored_user_turn_count, 1)

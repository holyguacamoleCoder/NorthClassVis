"""Teacher-visible chat transcript helpers (independent of LLM context compaction)."""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any

from runs.apply import strip_run_modify_from_user_content
from skills.message_meta import is_ui_hidden_message

_UI_SCOPE_BLOCK_RE = re.compile(
    r"\n*\s*\[系统[·・.]?UI\s*同步\][\s\S]*$",
    re.IGNORECASE,
)
_TURN_SCOPE_PREFIX_RE = re.compile(
    r"^\s*\[系统[·・.]?(?:本轮范围|附件上下文)\][\s\S]*?\n---\n教师本轮问题：\n",
    re.IGNORECASE,
)
_REMINDER_RE = re.compile(r"<reminder>[\s\S]*?</reminder>", re.IGNORECASE)


def clean_user_content_for_display(content: str) -> str:
    """Strip protocol / adapter injections from teacher-visible user text."""
    text = strip_run_modify_from_user_content(content)
    text = _REMINDER_RE.sub("", text)
    text = _TURN_SCOPE_PREFIX_RE.sub("", text)
    text = _UI_SCOPE_BLOCK_RE.sub("", text)
    return text.strip()


def _copy_message_for_ui(msg: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(msg)
    out.pop("_agent_meta", None)
    if out.get("role") == "user":
        out["content"] = clean_user_content_for_display(str(out.get("content") or ""))
    return out


def ensure_ui_messages_seeded(session: Any) -> None:
    """
    One-time seed: copy current LLM messages into ui_messages (skipping hidden).

    Call before a turn that may compact, so history is preserved for display.
    """
    if getattr(session, "ui_messages", None):
        return
    seeded: list[dict[str, Any]] = []
    for msg in list(getattr(session, "messages", None) or []):
        if not isinstance(msg, dict):
            continue
        if is_ui_hidden_message(msg):
            continue
        if msg.get("role") == "user":
            cleaned = clean_user_content_for_display(str(msg.get("content") or ""))
            if not cleaned:
                continue
            seeded.append({"role": "user", "content": cleaned})
            continue
        seeded.append(_copy_message_for_ui(msg))
    session.ui_messages = seeded


def append_ui_turn(
    session: Any,
    *,
    display_user_text: str,
    turn_messages: list[dict[str, Any]],
    ui_scope: dict[str, Any] | None = None,
) -> None:
    """
    Append one completed teacher turn to the durable UI transcript.

    ``display_user_text`` is the original teacher input (before UI-scope / reminder
    augmentation). ``turn_messages`` is the slice of LLM messages added this turn
    (including the augmented user message).
    """
    ensure_ui_messages_seeded(session)
    ui: list[dict[str, Any]] = session.ui_messages

    cleaned = clean_user_content_for_display(display_user_text)
    if cleaned:
        user_row: dict[str, Any] = {"role": "user", "content": cleaned}
        if ui_scope:
            user_row["ui_scope"] = dict(ui_scope)
        ui.append(user_row)

    saw_user = False
    for msg in turn_messages:
        if not isinstance(msg, dict):
            continue
        if is_ui_hidden_message(msg):
            continue
        role = msg.get("role")
        if role == "user":
            if not saw_user:
                saw_user = True
                continue
            extra = clean_user_content_for_display(str(msg.get("content") or ""))
            if extra:
                ui.append({"role": "user", "content": extra})
            continue
        ui.append(_copy_message_for_ui(msg))


def extract_latest_turn_messages(
    messages: list[dict[str, Any]],
    display_user_text: str,
) -> list[dict[str, Any]]:
    """
    Locate this turn's messages after possible mid-turn compaction.

    Compaction may rewrite the whole list, so index-based slicing is unsafe.
    """
    cleaned = clean_user_content_for_display(display_user_text)
    needle = (display_user_text or "").strip()
    start: int | None = None
    for i in range(len(messages) - 1, -1, -1):
        msg = messages[i]
        if msg.get("role") != "user" or is_ui_hidden_message(msg):
            continue
        body = clean_user_content_for_display(str(msg.get("content") or ""))
        raw = str(msg.get("content") or "")
        if (cleaned and body == cleaned) or (needle and raw.startswith(needle)):
            start = i
            break
    if start is None:
        for i in range(len(messages) - 1, -1, -1):
            if messages[i].get("role") == "user" and not is_ui_hidden_message(messages[i]):
                start = i
                break
    if start is None:
        return []
    return list(messages[start:])


def messages_for_ui(session: Any) -> list[dict[str, Any]]:
    """Prefer durable UI transcript; fall back to LLM messages for legacy sessions."""
    ui = getattr(session, "ui_messages", None) or []
    if ui:
        return list(ui)
    return list(getattr(session, "messages", None) or [])

"""Internal metadata on messages (stripped before LLM API)."""

from __future__ import annotations

from typing import Any

from .tool_result import (
    COMPACT_POLICY_PIN,
    CONTENT_KIND_COMPACT_SUMMARY,
    CONTENT_KIND_REFERENCE,
    CONTENT_KIND_SKILL,
    CONTENT_KIND_UI_SCOPE_HINT,
)


def attach_pin_meta(
    msg: dict[str, Any],
    *,
    content_kind: str,
    resource_id: str,
) -> dict[str, Any]:
    out = dict(msg)
    out["_agent_meta"] = {
        "compact_policy": COMPACT_POLICY_PIN,
        "content_kind": content_kind,
        "resource_id": resource_id,
    }
    return out


def attach_ui_hidden_meta(
    msg: dict[str, Any],
    *,
    content_kind: str,
) -> dict[str, Any]:
    """Mark synthetic user/system injections that must not appear in the chat UI."""
    out = dict(msg)
    meta = dict(out.get("_agent_meta") or {})
    meta["ui_visible"] = False
    meta["content_kind"] = content_kind
    out["_agent_meta"] = meta
    return out


def is_pinned_message(msg: dict[str, Any]) -> bool:
    meta = msg.get("_agent_meta")
    if isinstance(meta, dict) and meta.get("compact_policy") == COMPACT_POLICY_PIN:
        return True
    return False


def is_ui_hidden_message(msg: dict[str, Any]) -> bool:
    """True for synthetic context messages that should not render in the frontend."""
    meta = msg.get("_agent_meta")
    if isinstance(meta, dict) and meta.get("ui_visible") is False:
        return True
    if msg.get("role") != "user":
        return False
    text = str(msg.get("content") or "").lstrip()
    if not text:
        return False
    # Legacy sessions: compact / continuation injected before meta existed.
    from common.prompts import COMPACT_USER_MESSAGE_PREAMBLE, OUTPUT_CONTINUATION_MESSAGE

    if text.startswith(COMPACT_USER_MESSAGE_PREAMBLE):
        return True
    if text.startswith(OUTPUT_CONTINUATION_MESSAGE[:40]):
        return True
    return False


def is_compact_summary_message(msg: dict[str, Any]) -> bool:
    meta = msg.get("_agent_meta")
    if isinstance(meta, dict) and meta.get("content_kind") == CONTENT_KIND_COMPACT_SUMMARY:
        return True
    if msg.get("role") != "user":
        return False
    from common.prompts import COMPACT_USER_MESSAGE_PREAMBLE

    return str(msg.get("content") or "").lstrip().startswith(COMPACT_USER_MESSAGE_PREAMBLE)


def is_ui_scope_hint_message(msg: dict[str, Any]) -> bool:
    meta = msg.get("_agent_meta")
    if isinstance(meta, dict) and meta.get("content_kind") == CONTENT_KIND_UI_SCOPE_HINT:
        return True
    if msg.get("role") != "user":
        return False
    text = str(msg.get("content") or "").lstrip()
    return text.startswith("[系统·本轮范围]") or text.startswith("[系统·附件上下文]")


def drop_previous_ui_scope_hints(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep at most the latest turn's scope hint in LLM context (avoid stacking)."""
    return [m for m in messages if not is_ui_scope_hint_message(m)]


def pin_meta_for_tool(tool_name: str, content: str) -> dict[str, Any] | None:
    from .tool_result import is_fresh_reference_load, is_fresh_skill_load

    if tool_name == "load_skill" and is_fresh_skill_load(content):
        # resource_id filled by caller when known
        return {
            "compact_policy": COMPACT_POLICY_PIN,
            "content_kind": CONTENT_KIND_SKILL,
        }
    if tool_name == "load_reference" and is_fresh_reference_load(content):
        return {
            "compact_policy": COMPACT_POLICY_PIN,
            "content_kind": CONTENT_KIND_REFERENCE,
        }
    return None


def strip_internal_message_keys(msg: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in msg.items() if not str(k).startswith("_")}

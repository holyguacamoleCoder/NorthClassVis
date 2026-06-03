"""Internal metadata on messages (stripped before LLM API)."""

from __future__ import annotations

from typing import Any

from .tool_result import COMPACT_POLICY_PIN, CONTENT_KIND_REFERENCE, CONTENT_KIND_SKILL


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


def is_pinned_message(msg: dict[str, Any]) -> bool:
    meta = msg.get("_agent_meta")
    if isinstance(meta, dict) and meta.get("compact_policy") == COMPACT_POLICY_PIN:
        return True
    return False


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

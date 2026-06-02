"""Parse memory tool results for HTTP progress and UI."""

from __future__ import annotations

import re
from typing import Any

_MEMORY_RESULT_RE = re.compile(
    r"\[Memory\s+(?P<verb>saved|updated|removed):\s*(?P<body>[^\]]+)\]",
    re.IGNORECASE,
)
_KV_RE = re.compile(r"(\w+)=([^,]+)")


def parse_memory_tool_result(content: str) -> dict[str, Any] | None:
    """Extract structured memory event from tool result text."""
    text = (content or "").strip()
    if not text or text.startswith("Error:"):
        return None
    match = _MEMORY_RESULT_RE.search(text)
    if not match:
        return None
    verb = match.group("verb").lower()
    body = match.group("body")
    fields: dict[str, str] = {}
    for key, value in _KV_RE.findall(body):
        fields[key.strip()] = value.strip()
    action = fields.get("action") or ("removed" if verb == "removed" else "saved")
    event: dict[str, Any] = {
        "action": action,
        "label": _memory_event_label(fields, verb),
    }
    if fields.get("name"):
        event["name"] = fields["name"]
    if fields.get("type"):
        event["type"] = fields["type"]
    if fields.get("target"):
        event["target"] = fields["target"]
    if fields.get("path"):
        event["path"] = fields["path"]
    return event


def _memory_event_label(fields: dict[str, str], verb: str) -> str:
    if fields.get("name"):
        return str(fields["name"])
    if fields.get("target"):
        return str(fields["target"])
    return verb


def memory_event_from_tool(
    tool_name: str,
    content: str,
    params: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    if tool_name not in ("memory", "save_memory"):
        return None
    if (content or "").strip().startswith("Error"):
        return None
    event = parse_memory_tool_result(content)
    if event is None:
        return None
    params = params or {}
    if tool_name == "memory" and not event.get("target"):
        target = params.get("target")
        if target:
            event["target"] = str(target)
        act = params.get("action")
        if act:
            event["action"] = str(act)
    if tool_name == "save_memory" and not event.get("name"):
        name = params.get("name")
        if name:
            event["name"] = str(name)
    return event

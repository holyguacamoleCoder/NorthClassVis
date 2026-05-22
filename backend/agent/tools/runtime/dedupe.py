import json
import logging
from typing import Any

from common.logger import get_logger, log_event

_log = get_logger("tools")


def parse_args(raw_args: Any) -> dict[str, Any]:
    if isinstance(raw_args, str):
        try:
            return json.loads(raw_args) if raw_args else {}
        except (TypeError, ValueError):
            return {}
    if isinstance(raw_args, dict):
        return raw_args
    return {}


def _tool_call_key(call: dict[str, Any]) -> tuple[str, str]:
    name = str(call.get("name") or "")
    args = parse_args(call.get("arguments", {}))
    return name, json.dumps(args, sort_keys=True, ensure_ascii=False)


def dedupe_tool_calls(tool_calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Drop identical tool+args duplicates within one LLM batch."""
    seen: set[tuple[str, str]] = set()
    out: list[dict[str, Any]] = []
    for call in tool_calls:
        key = _tool_call_key(call)
        if key in seen:
            log_event(
                _log,
                logging.INFO,
                "tool_call_deduped",
                tool=key[0],
            )
            continue
        seen.add(key)
        out.append(call)
    return out

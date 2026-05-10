import json
import logging
from typing import Any

from common.logger import get_logger, log_event, truncate_for_log

from .registry import TOOL_DISPATCHER

_log = get_logger("tools")


def _parse_args(raw_args: Any) -> dict[str, Any]:
    if isinstance(raw_args, str):
        try:
            return json.loads(raw_args) if raw_args else {}
        except (TypeError, ValueError):
            return {}
    if isinstance(raw_args, dict):
        return raw_args
    return {}


def execute_tool_calls(tool_calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    tool_results = []
    # 处理每一个调用
    for call in tool_calls:
        tool_name = call.get("name")
        call_id = call.get("id")
        parsed_args = _parse_args(call.get("arguments", {}))

        # 是一个不存在的工具调用
        if tool_name not in TOOL_DISPATCHER:
            log_event(
                _log,
                logging.WARNING,
                "tool_unknown",
                tool=tool_name,
                tool_call_id=call_id,
            )
            tool_results.append(
                {
                    "role": "tool",
                    "tool_call_id": call_id,
                    "content": f"Error: Tool {tool_name} not found",
                }
            )
            continue

        log_event(
            _log,
            logging.DEBUG,
            "tool_dispatch",
            tool=tool_name,
            tool_call_id=call_id,
            args_preview=truncate_for_log(parsed_args),
        )
        try:
            tool_result = TOOL_DISPATCHER[tool_name](**parsed_args)
        except Exception:
            _log.exception(
                "tool_exec_failed tool=%s tool_call_id=%s",
                tool_name,
                call_id,
            )
            tool_results.append(
                {
                    "role": "tool",
                    "tool_call_id": call_id,
                    "content": f"Error: Tool {tool_name} execution failed",
                }
            )
            continue

        log_event(
            _log,
            logging.INFO,
            "tool_result",
            tool=tool_name,
            tool_call_id=call_id,
            result_preview=truncate_for_log(tool_result),
        )
        tool_results.append(
            {
                "role": "tool",
                "tool_call_id": call_id,
                "content": tool_result,
            }
        )
    return tool_results

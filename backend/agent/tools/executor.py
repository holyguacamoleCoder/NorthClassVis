import json
import logging
from typing import Any

from common.logger import get_logger, log_event, truncate_for_log
from context import maybe_persist_output, track_recent_file
from context.config import DEFAULT_CONFIG
from context.state import CompactState

from .registry import TOOL_DISPATCHER

_log = get_logger("tools")

from permission import PermissionManager


def _parse_args(raw_args: Any) -> dict[str, Any]:
    if isinstance(raw_args, str):
        try:
            return json.loads(raw_args) if raw_args else {}
        except (TypeError, ValueError):
            return {}
    if isinstance(raw_args, dict):
        return raw_args
    return {}


_PATH_TOOLS = frozenset({"read_file", "list_files"})


def execute_tool_calls(
    tool_calls: list[dict[str, Any]],
    *,
    compact_state: CompactState | None = None,
    permission: "PermissionManager | None" = None,
) -> list[dict[str, Any]]:
    tool_results = []
    # 处理每一个调用
    for call in tool_calls:
        tool_name = call.get("name")
        call_id = call.get("id")
        parsed_args = _parse_args(call.get("arguments", {}))

        if permission is not None:
            decision = permission.check(tool_name, parsed_args)
            behavior = decision.get("behavior")
            if behavior == "deny":
                reason = decision.get("reason", "denied")
                log_event(
                    _log,
                    logging.INFO,
                    "tool_denied",
                    tool=tool_name,
                    tool_call_id=call_id,
                    mode=getattr(permission.mode, "value", permission.mode),
                    reason=reason,
                )
                tool_results.append(
                    {
                        "role": "tool",
                        "tool_call_id": call_id,
                        "content": f"Permission denied: {reason}",
                    }
                )
                continue
            if behavior == "ask":
                reason = decision.get("reason", "approval required")
                if not permission.ask_user(tool_name, parsed_args, reason):
                    log_event(
                        _log,
                        logging.INFO,
                        "tool_denied_user",
                        tool=tool_name,
                        tool_call_id=call_id,
                        mode=getattr(permission.mode, "value", permission.mode),
                        reason=reason,
                    )
                    content = (
                        f"Permission denied for {tool_name}: {reason}. "
                        "Approval was not granted (use an interactive client or adjust rules/mode)."
                    )
                    tool_results.append(
                        {
                            "role": "tool",
                            "tool_call_id": call_id,
                            "content": content,
                        }
                    )
                    continue

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

        if compact_state and tool_name in _PATH_TOOLS:
            path_arg = parsed_args.get("path") or "."
            track_recent_file(
                compact_state,
                str(path_arg),
                max_files=DEFAULT_CONFIG.max_recent_files,
            )

        if call_id and isinstance(tool_result, str):
            tool_result = maybe_persist_output(call_id, tool_result)

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

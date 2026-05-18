import json
import logging
from typing import TYPE_CHECKING, Any

from common.logger import get_logger, log_event, truncate_for_log
from context import maybe_persist_output, track_recent_file
from context.config import DEFAULT_CONFIG
from context.state import CompactState

from .registry import TOOL_DISPATCHER

_log = get_logger("tools")

from permission import PermissionManager

if TYPE_CHECKING:
    from hooks import HookManager


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


def _prepend_hook_messages(content: str, messages: list[str]) -> str:
    if not messages:
        return content
    prefix = "\n".join(f"[Hook message]: {m}" for m in messages)
    if content:
        return f"{prefix}\n\n{content}"
    return prefix


def _append_hook_notes(content: str, messages: list[str]) -> str:
    if not messages:
        return content
    notes = "\n".join(f"[Hook note]: {m}" for m in messages)
    if content:
        return f"{content}\n{notes}"
    return notes


def execute_tool_calls(
    tool_calls: list[dict[str, Any]],
    *,
    compact_state: CompactState | None = None,
    permission: PermissionManager | None = None,
    hooks: "HookManager | None" = None,
) -> list[dict[str, Any]]:
    tool_results = []
    for call in tool_calls:
        tool_name = call.get("name")
        call_id = call.get("id")
        parsed_args = _parse_args(call.get("arguments", {}))
        pre_messages: list[str] = []

        if hooks is not None:
            ctx: dict[str, Any] = {
                "tool_name": tool_name or "",
                "tool_input": dict(parsed_args),
            }
            pre_result = hooks.run_hooks("PreToolUse", ctx)
            pre_messages.extend(pre_result.messages)
            parsed_args = _parse_args(ctx.get("tool_input", parsed_args))

            if pre_result.blocked:
                reason = pre_result.block_reason or "Blocked by hook"
                content = _prepend_hook_messages(
                    f"Tool blocked by PreToolUse hook: {reason}",
                    pre_messages,
                )
                log_event(
                    _log,
                    logging.INFO,
                    "tool_blocked_hook",
                    tool=tool_name,
                    tool_call_id=call_id,
                    reason=reason,
                )
                tool_results.append(
                    {
                        "role": "tool",
                        "tool_call_id": call_id,
                        "content": content,
                    }
                )
                continue

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
                        "content": _prepend_hook_messages(
                            f"Permission denied: {reason}",
                            pre_messages,
                        ),
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
                    content = _prepend_hook_messages(
                        (
                            f"Permission denied for {tool_name}: {reason}. "
                            "Approval was not granted (use an interactive client or adjust rules/mode)."
                        ),
                        pre_messages,
                    )
                    tool_results.append(
                        {
                            "role": "tool",
                            "tool_call_id": call_id,
                            "content": content,
                        }
                    )
                    continue

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
                    "content": _prepend_hook_messages(
                        f"Error: Tool {tool_name} not found",
                        pre_messages,
                    ),
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
                    "content": _prepend_hook_messages(
                        f"Error: Tool {tool_name} execution failed",
                        pre_messages,
                    ),
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

        if hooks is not None:
            post_ctx: dict[str, Any] = {
                "tool_name": tool_name or "",
                "tool_input": dict(parsed_args),
                "tool_output": tool_result,
            }
            post_result = hooks.run_hooks("PostToolUse", post_ctx)
            tool_result = _append_hook_notes(tool_result, post_result.messages)

        tool_result = _prepend_hook_messages(tool_result, pre_messages)

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

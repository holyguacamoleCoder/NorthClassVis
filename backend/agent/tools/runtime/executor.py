import logging
from typing import TYPE_CHECKING, Any

import runtime_bootstrap  # noqa: F401

from common.logger import get_logger, log_event, truncate_for_log
from context.state import CompactState
from loop_state import AnalysisToolContext
from permission import PermissionManager

from ..definitions.registry import TOOL_DISPATCHER
from .data_chain import inject_data_tool_context
from .dedupe import dedupe_tool_calls, parse_args
from .hooks_io import append_hook_notes, prepend_hook_messages
from .permission_io import allowed_tool_names, permission_denied_content
from .postprocess import log_tool_repair, postprocess_tool_result, prepend_repair_notes
from .repair import repair_tool_call

_log = get_logger("tools")

if TYPE_CHECKING:
    from hooks import HookManager


def execute_tool_calls(
    tool_calls: list[dict[str, Any]],
    *,
    compact_state: CompactState | None = None,
    permission: PermissionManager | None = None,
    hooks: "HookManager | None" = None,
    analysis_context: AnalysisToolContext | None = None,
) -> list[dict[str, Any]]:
    tool_calls = dedupe_tool_calls(tool_calls)
    tool_results: list[dict[str, Any]] = []
    batch_query_refs: list[str] = []

    for call in tool_calls:
        tool_name = call.get("name")
        call_id = call.get("id")
        parsed_args = parse_args(call.get("arguments", {}))
        pre_messages: list[str] = []

        if hooks is not None:
            ctx: dict[str, Any] = {
                "tool_name": tool_name or "",
                "tool_input": dict(parsed_args),
            }
            pre_result = hooks.run_hooks("PreToolUse", ctx)
            pre_messages.extend(pre_result.messages)
            parsed_args = parse_args(ctx.get("tool_input", parsed_args))

            if pre_result.blocked:
                reason = pre_result.block_reason or "Blocked by hook"
                content = prepend_hook_messages(
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

        # 规范化工具名/参数：每条未 blocked 的调用都会执行，仅在有 typo、别名或可选默认值时改写；
        # 放在 permission 之前，使修正后的名称参与 allowlist 校验（如 QueryData→query_data）。
        repair = repair_tool_call(
            tool_name,
            parsed_args,
            allowed_names=allowed_tool_names(permission),
            dispatcher_keys=frozenset(TOOL_DISPATCHER),
        )
        log_tool_repair(repair, tool_call_id=call_id, permission=permission)
        if repair.name:
            tool_name = repair.name
            parsed_args = repair.args

        if repair.missing_required:
            missing = ", ".join(sorted(repair.missing_required))
            log_event(
                _log,
                logging.INFO,
                "tool_missing_required",
                tool=tool_name,
                tool_call_id=call_id,
                missing=missing,
            )
            tool_results.append(
                {
                    "role": "tool",
                    "tool_call_id": call_id,
                    "content": prepend_hook_messages(
                        prepend_repair_notes(
                            f"Error: Missing required arguments for {tool_name}: {missing}",
                            repair.notes,
                        ),
                        pre_messages,
                    ),
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
                        "content": permission_denied_content(
                            hooks=hooks,
                            permission=permission,
                            tool_name=tool_name,
                            parsed_args=parsed_args,
                            reason=reason,
                            pre_messages=pre_messages,
                            deny_type="policy",
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
                    content = permission_denied_content(
                        hooks=hooks,
                        permission=permission,
                        tool_name=tool_name,
                        parsed_args=parsed_args,
                        reason=(
                            f"{reason}. Approval was not granted "
                            "(use an interactive client or adjust rules/mode)."
                        ),
                        pre_messages=pre_messages,
                        deny_type="approval",
                        message_prefix=f"Permission denied for {tool_name}",
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
            display = repair.original_name or tool_name
            hint = f"Error: Tool {display!r} not found."
            if repair.suggestions:
                hint += f" Did you mean: {', '.join(repair.suggestions)}?"
            log_event(
                _log,
                logging.WARNING,
                "tool_unknown",
                tool=display,
                tool_call_id=call_id,
                suggestions=repair.suggestions or None,
            )
            tool_results.append(
                {
                    "role": "tool",
                    "tool_call_id": call_id,
                    "content": prepend_hook_messages(
                        prepend_repair_notes(hint, repair.notes),
                        pre_messages,
                    ),
                }
            )
            continue

        dispatch_args = inject_data_tool_context(
            tool_name,
            parsed_args,
            analysis_context=analysis_context,
            batch_query_refs=batch_query_refs,
        )

        log_event(
            _log,
            logging.DEBUG,
            "tool_dispatch",
            tool=tool_name,
            tool_call_id=call_id,
            args_preview=truncate_for_log(
                {k: v for k, v in dispatch_args.items() if not k.startswith("_")}
            ),
        )
        try:
            tool_result = TOOL_DISPATCHER[tool_name](**dispatch_args)
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
                    "content": prepend_hook_messages(
                        f"Error: Tool {tool_name} execution failed",
                        pre_messages,
                    ),
                }
            )
            continue

        tool_result = postprocess_tool_result(
            tool_name,
            tool_result,
            call_id=call_id,
            parsed_args=parsed_args,
            compact_state=compact_state,
            analysis_context=analysis_context,
            batch_query_refs=batch_query_refs,
        )

        if hooks is not None:
            post_ctx: dict[str, Any] = {
                "tool_name": tool_name or "",
                "tool_input": dict(parsed_args),
                "tool_output": tool_result,
            }
            post_result = hooks.run_hooks("PostToolUse", post_ctx)
            tool_result = append_hook_notes(tool_result, post_result.messages)

        tool_result = prepend_repair_notes(
            prepend_hook_messages(tool_result, pre_messages),
            repair.notes,
        )

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

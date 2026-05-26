import logging
from typing import TYPE_CHECKING, Any, Callable

import runtime_bootstrap  # noqa: F401

from common.langfuse_tracing import end_tool_span, is_tool_result_error, tool_span
from common.logger import get_logger, log_event, truncate_for_log
from context.state import CompactState
from loop_state import AnalysisToolContext, QuerySnapshot
from permission import PermissionManager

from ..definitions.registry import TOOL_DISPATCHER
from .data.inject import inject_data_tool_context
from .data.ordering import partition_tool_calls_for_data_pipeline
from .pipeline.hooks import append_hook_notes, prepend_hook_messages
from .pipeline.permission import allowed_tool_names, permission_denied_content
from .pipeline.postprocess import log_tool_repair, postprocess_tool_result, prepend_repair_notes
from .pipeline.preprocess import dedupe_tool_calls, parse_args
from .pipeline.repair import repair_tool_call

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
    loaded_skills: set[str] | None = None,
    llm_client: Any | None = None,
    filter_context: Any | None = None,
    on_tool_event: Callable[[dict[str, Any]], None] | None = None,
) -> list[dict[str, Any]]:
    tool_calls = dedupe_tool_calls(tool_calls)
    batch_snapshots: list[QuerySnapshot] = []
    results_by_id: dict[str, dict[str, Any]] = {}

    queries, rest = partition_tool_calls_for_data_pipeline(tool_calls)
    execution_order = queries + rest

    for call in execution_order:
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
                if call_id:
                    if on_tool_event and tool_name:
                        on_tool_event({
                            "type": "tool_start",
                            "call_id": str(call_id),
                            "tool": str(tool_name or ""),
                            "params": dict(parsed_args),
                        })
                        on_tool_event({
                            "type": "tool_end",
                            "call_id": str(call_id),
                            "tool": str(tool_name or ""),
                            "params": dict(parsed_args),
                            "content": content,
                        })
                    results_by_id[call_id] = {
                        "role": "tool",
                        "tool_call_id": call_id,
                        "content": content,
                    }
                continue

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

        def _emit_start() -> None:
            if on_tool_event and call_id and tool_name:
                on_tool_event({
                    "type": "tool_start",
                    "call_id": str(call_id),
                    "tool": str(tool_name),
                    "params": dict(parsed_args),
                })

        def _store(content: str) -> None:
            if not call_id:
                return
            results_by_id[call_id] = {
                "role": "tool",
                "tool_call_id": call_id,
                "content": content,
            }
            if on_tool_event and tool_name:
                on_tool_event({
                    "type": "tool_end",
                    "call_id": str(call_id),
                    "tool": str(tool_name),
                    "params": dict(parsed_args),
                    "content": content,
                })

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
            if call_id:
                _emit_start()
                _store(
                    prepend_hook_messages(
                        prepend_repair_notes(
                            f"Error: Missing required arguments for {tool_name}: {missing}",
                            repair.notes,
                        ),
                        pre_messages,
                    )
                )
            continue

        _emit_start()

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
                if call_id:
                    _store(
                        permission_denied_content(
                            hooks=hooks,
                            permission=permission,
                            tool_name=tool_name,
                            parsed_args=parsed_args,
                            reason=reason,
                            pre_messages=pre_messages,
                            deny_type="policy",
                        )
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
                    if call_id:
                        _store(content)
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
            if call_id:
                _store(
                    prepend_hook_messages(
                        prepend_repair_notes(hint, repair.notes),
                        pre_messages,
                    )
                )
            continue

        dispatch_args = inject_data_tool_context(
            tool_name,
            parsed_args,
            analysis_context=analysis_context,
            batch_snapshots=batch_snapshots,
            llm_client=llm_client,
            filter_context=filter_context,
        )
        if tool_name == "load_skill" and loaded_skills is not None:
            dispatch_args = {**dispatch_args, "_loaded_skills": loaded_skills}

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
        tool_result = ""
        with tool_span(tool=tool_name or "unknown", params=parsed_args) as lf_span:
            try:
                tool_result = TOOL_DISPATCHER[tool_name](**dispatch_args)
            except Exception:
                _log.exception(
                    "tool_exec_failed tool=%s tool_call_id=%s",
                    tool_name,
                    call_id,
                )
                tool_result = f"Error: Tool {tool_name} execution failed"
                end_tool_span(lf_span, output=tool_result, is_error=True)
                if call_id:
                    _store(
                        prepend_hook_messages(
                            tool_result,
                            pre_messages,
                        )
                    )
                continue

            tool_result = postprocess_tool_result(
                tool_name,
                tool_result,
                call_id=call_id,
                parsed_args=parsed_args,
                compact_state=compact_state,
                analysis_context=analysis_context,
                batch_snapshots=batch_snapshots,
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
            end_tool_span(
                lf_span,
                output=tool_result if isinstance(tool_result, str) else str(tool_result),
                is_error=is_tool_result_error(
                    tool_result if isinstance(tool_result, str) else ""
                ),
            )

        log_event(
            _log,
            logging.INFO,
            "tool_result",
            tool=tool_name,
            tool_call_id=call_id,
            result_preview=truncate_for_log(tool_result),
        )
        if call_id:
            _store(tool_result)

    tool_results: list[dict[str, Any]] = []
    for call in tool_calls:
        call_id = call.get("id")
        if call_id and call_id in results_by_id:
            tool_results.append(results_by_id[call_id])
    return tool_results

import json
import logging
from typing import TYPE_CHECKING, Any

from common.logger import get_logger, log_event, truncate_for_log
from context import maybe_persist_output, track_recent_file
from context.config import DEFAULT_CONFIG
from context.state import CompactState
from context.tool_result_summary import append_query_summary_to_result

from .analysis_context import AnalysisToolContext
from .registry import TOOL_DISPATCHER
from .tool_repair import ToolRepairResult, repair_tool_call

_log = get_logger("tools")

from permission import PermissionManager
from permission.modes import MODE_TOOL_ALLOWLIST

if TYPE_CHECKING:
    from hooks import HookManager

_PATH_TOOLS = frozenset({"read_file", "list_files"})
_DATA_CHAIN_TOOLS = frozenset({"query_data", "aggregate_data", "inspect_schema"})


def _parse_args(raw_args: Any) -> dict[str, Any]:
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
    args = _parse_args(call.get("arguments", {}))
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


def _prepend_repair_notes(content: str, notes: list[str]) -> str:
    if not notes:
        return content
    prefix = "\n".join(notes)
    if content:
        return f"{prefix}\n\n{content}"
    return prefix


def _log_tool_repair(
    repair: ToolRepairResult,
    *,
    tool_call_id: str | None,
    permission: PermissionManager | None,
) -> None:
    if not repair.was_repaired:
        return
    mode = ""
    if permission is not None:
        mode = getattr(permission.mode, "value", permission.mode)
        if not isinstance(mode, str):
            mode = str(mode)
    log_event(
        _log,
        logging.INFO,
        "tool_repaired",
        tool_call_id=tool_call_id,
        original_tool=repair.original_name,
        canonical_tool=repair.name,
        confidence=repair.confidence,
        permission_mode=mode or None,
        notes=repair.notes,
        missing_required=sorted(repair.missing_required) or None,
    )


def _allowed_tool_names(permission: PermissionManager | None) -> frozenset[str]:
    if permission is not None:
        return MODE_TOOL_ALLOWLIST.get(permission.mode, frozenset())
    return frozenset(TOOL_DISPATCHER)


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


def _permission_denied_content(
    *,
    hooks: "HookManager | None",
    permission: PermissionManager | None,
    tool_name: str | None,
    parsed_args: dict[str, Any],
    reason: str,
    pre_messages: list[str],
    deny_type: str = "policy",
    message_prefix: str = "Permission denied",
) -> str:
    base = f"{message_prefix}: {reason}"
    if hooks is None:
        return _prepend_hook_messages(base, pre_messages)

    mode = ""
    if permission is not None:
        mode = getattr(permission.mode, "value", permission.mode)
        if not isinstance(mode, str):
            mode = str(mode)

    deny_result = hooks.run_hooks(
        "PermissionDeny",
        {
            "tool_name": tool_name or "",
            "tool_input": dict(parsed_args),
            "deny_reason": reason,
            "permission_mode": mode,
            "deny_type": deny_type,
        },
    )
    hook_messages = list(deny_result.messages)
    if deny_result.blocked and deny_result.block_reason:
        hook_messages.append(deny_result.block_reason)
    return _prepend_hook_messages(base, pre_messages + hook_messages)


def _inject_data_tool_context(
    tool_name: str | None,
    parsed_args: dict[str, Any],
    *,
    analysis_context: AnalysisToolContext | None,
    batch_query_refs: list[str],
) -> dict[str, Any]:
    args = dict(parsed_args)
    if tool_name not in _DATA_CHAIN_TOOLS:
        return args

    if tool_name == "aggregate_data" and not args.get("input"):
        if batch_query_refs:
            args["input"] = {"result_ref": batch_query_refs[-1]}
            args["_auto_input"] = True
        elif analysis_context and analysis_context.last_result_ref:
            args["input"] = {"result_ref": analysis_context.last_result_ref}
            args["_auto_input"] = True

    if analysis_context and analysis_context.last_result_ref:
        args["_last_result_ref"] = analysis_context.last_result_ref

    return args


def _record_query_result(
    tool_result: str,
    *,
    analysis_context: AnalysisToolContext | None,
    batch_query_refs: list[str],
) -> None:
    if not tool_result or tool_result.startswith("Error:"):
        return
    try:
        payload = json.loads(tool_result)
    except json.JSONDecodeError:
        return
    if not isinstance(payload, dict):
        return
    ref = (payload.get("meta") or {}).get("result_ref")
    if ref:
        batch_query_refs.append(str(ref))
    if analysis_context is not None:
        analysis_context.note_query_result(payload)


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

    # 处理每一个tool call
    for call in tool_calls:
        # 获取tool信息
        tool_name = call.get("name")
        call_id = call.get("id")
        parsed_args = _parse_args(call.get("arguments", {}))
        pre_messages: list[str] = []

        # 执行hook：PreToolUse
        if hooks is not None:
            ctx: dict[str, Any] = {
                "tool_name": tool_name or "",
                "tool_input": dict(parsed_args),
            }
            pre_result = hooks.run_hooks("PreToolUse", ctx)
            pre_messages.extend(pre_result.messages)
            parsed_args = _parse_args(ctx.get("tool_input", parsed_args))

            # 如果hook被阻塞，则记录错误
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

        # 规范化工具名/参数：每条未 blocked 的调用都会执行，仅在有 typo、别名或可选默认值时改写；
        # 放在 permission 之前，使修正后的名称参与 allowlist 校验（如 QueryData→query_data）。
        repair = repair_tool_call(
            tool_name,
            parsed_args,
            allowed_names=_allowed_tool_names(permission),
            dispatcher_keys=frozenset(TOOL_DISPATCHER),
        )
        _log_tool_repair(repair, tool_call_id=call_id, permission=permission)
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
                    "content": _prepend_hook_messages(
                        _prepend_repair_notes(
                            f"Error: Missing required arguments for {tool_name}: {missing}",
                            repair.notes,
                        ),
                        pre_messages,
                    ),
                }
            )
            continue

        # 执行权限检查
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
                        "content": _permission_denied_content(
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
                    content = _permission_denied_content(
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
                    "content": _prepend_hook_messages(
                        _prepend_repair_notes(hint, repair.notes),
                        pre_messages,
                    ),
                }
            )
            continue

        dispatch_args = _inject_data_tool_context(
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
                    "content": _prepend_hook_messages(
                        f"Error: Tool {tool_name} execution failed",
                        pre_messages,
                    ),
                }
            )
            continue

        if tool_name == "query_data" and isinstance(tool_result, str):
            _record_query_result(
                tool_result,
                analysis_context=analysis_context,
                batch_query_refs=batch_query_refs,
            )
            # 在完整 JSON 前加入：
            # [Summary] resource=..., result_ref=..., rows_scanned=...
            # 作用：
            # 当下：模型一眼看到关键元数据，不必先啃整段 JSON。
            # 之后：micro_compact 会把旧的 tool 正文换成占位符，但会尽量 保留这行 [Summary]（extract_tabular_summary / compact_tool_content），压缩后仍知道 result_ref 等信息。
            tool_result = append_query_summary_to_result(tool_result)

        # 记录追踪最近文件，LRU式更新
        if compact_state and tool_name in _PATH_TOOLS:
            path_arg = parsed_args.get("path") or "."
            track_recent_file(
                compact_state,
                str(path_arg),
                max_files=DEFAULT_CONFIG.max_recent_files,
            )

        # 超长输出落盘
        if call_id and isinstance(tool_result, str):
            tool_result = maybe_persist_output(call_id, tool_result)


        # 执行hooks：PostToolUse
        if hooks is not None:
            post_ctx: dict[str, Any] = {
                "tool_name": tool_name or "",
                "tool_input": dict(parsed_args),
                "tool_output": tool_result,
            }
            post_result = hooks.run_hooks("PostToolUse", post_ctx)
            tool_result = _append_hook_notes(tool_result, post_result.messages)

        tool_result = _prepend_repair_notes(
            _prepend_hook_messages(tool_result, pre_messages),
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

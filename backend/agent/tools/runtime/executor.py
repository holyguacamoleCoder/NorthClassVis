import logging
from typing import TYPE_CHECKING, Any, Callable

import runtime_bootstrap  # noqa: F401

from common.langfuse_tracing import end_tool_span, is_tool_result_error, tool_span
from common.logger import get_logger, log_event, truncate_for_log
from context.state import CompactState
from loop_state import AnalysisToolContext, QuerySnapshot
from permission import PermissionManager
from runs.apply import apply_derive_plan_to_params, extract_run_meta_from_result
from runs.models import DATA_RUN_TOOLS

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
    from runs.registry import RunRegistry


def _apply_modify_context(
    tool_name: str | None,
    parsed_args: dict[str, Any],
    *,
    modify_context: dict[str, Any] | None,
    run_registry: "RunRegistry | None",
) -> dict[str, Any]:
    if not tool_name or run_registry is None:
        return parsed_args

    args = dict(parsed_args)
    derive_id = args.pop("derive_from_run_id", None)
    patch = dict(args.pop("patch", None) or {})

    parent_run_id: str | None = None
    if derive_id:
        parent_run_id = str(derive_id)
    elif modify_context and not modify_context.get("_consumed"):
        strategy = modify_context.get("strategy")
        if tool_name == "query_data" and strategy in (None, "requery"):
            parent_run_id = str(modify_context["parent_run_id"])
            patch = dict(modify_context.get("patch") or {})
        elif tool_name == "aggregate_data" and strategy in ("reaggregate", "reuse_aggregate"):
            parent_run_id = str(modify_context["parent_run_id"])
            patch = dict(modify_context.get("patch") or {})

    if not parent_run_id:
        return parsed_args

    parent_run = run_registry.get_run(parent_run_id)
    plan = run_registry.derive_run(parent_run_id, patch)
    if plan is None:
        return parsed_args

    merged = apply_derive_plan_to_params(
        tool_name,
        args,
        plan,
        parent_run=parent_run,
    )
    if modify_context is not None:
        modify_context["_consumed"] = True
        modify_context["_child_pending_parent"] = parent_run_id
    merged["_pending_supersede_parent"] = parent_run_id
    return merged


def _modify_blocks_query(
    tool_name: str | None,
    modify_context: dict[str, Any] | None,
) -> bool:
    if not tool_name or tool_name != "query_data" or not modify_context:
        return False
    if modify_context.get("_consumed"):
        return False
    return modify_context.get("strategy") in ("reaggregate", "reuse_aggregate")


def execute_tool_calls(
    tool_calls: list[dict[str, Any]],
    *,
    compact_state: CompactState | None = None,
    permission: PermissionManager | None = None,
    hooks: "HookManager | None" = None,
    analysis_context: AnalysisToolContext | None = None,
    loaded_skills: set[str] | None = None,
    loaded_references: set[str] | None = None,
    llm_client: Any | None = None,
    llm_router: Any | None = None,
    filter_context: Any | None = None,
    on_tool_event: Callable[[dict[str, Any]], None] | None = None,
    run_registry: "RunRegistry | None" = None,
    job_id: str | None = None,
    modify_context: dict[str, Any] | None = None,
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

        parsed_args = _apply_modify_context(
            tool_name,
            parsed_args,
            modify_context=modify_context,
            run_registry=run_registry,
        )

        if _modify_blocks_query(tool_name, modify_context):
            blocked = (
                "Error: 本轮为 reaggregate 修改，禁止调用 query_data。"
                "请直接调用 aggregate_data，使用系统注入的 input.dataset_id / result_ref，"
                "并应用 patch 中的 metrics / dimensions。"
            )
            if call_id:
                if on_tool_event and tool_name:
                    on_tool_event({
                        "type": "tool_start",
                        "call_id": str(call_id),
                        "tool": str(tool_name),
                        "params": {
                            k: v for k, v in parsed_args.items() if not str(k).startswith("_")
                        },
                    })
                    on_tool_event({
                        "type": "tool_end",
                        "call_id": str(call_id),
                        "tool": str(tool_name),
                        "params": {
                            k: v for k, v in parsed_args.items() if not str(k).startswith("_")
                        },
                        "content": blocked,
                    })
                results_by_id[call_id] = {
                    "role": "tool",
                    "tool_call_id": call_id,
                    "content": blocked,
                }
                continue

        run_id: str | None = None
        run_parent_id = parsed_args.get("_pending_supersede_parent")
        run_patch = parsed_args.get("_derive_patch")
        run_strategy = parsed_args.get("_derive_strategy")
        session_id = getattr(analysis_context, "session_id", None) if analysis_context else None
        user_turn = getattr(analysis_context, "user_turn", 0) if analysis_context else 0

        if (
            run_registry is not None
            and tool_name in DATA_RUN_TOOLS
            and session_id
        ):
            public_params = {
                k: v for k, v in parsed_args.items() if not str(k).startswith("_")
            }
            run_id = run_registry.begin_run(
                session_id=str(session_id),
                tool_name=str(tool_name),
                params=public_params,
                job_id=job_id,
                tool_call_id=str(call_id) if call_id else None,
                user_turn=int(user_turn),
                parent_run_id=str(run_parent_id) if run_parent_id else None,
                patch=dict(run_patch) if isinstance(run_patch, dict) else None,
                derive_strategy=str(run_strategy) if run_strategy else None,
            )
            if run_parent_id:
                run_registry.mark_superseded(str(run_parent_id), run_id)

        def _run_meta() -> dict[str, Any]:
            meta: dict[str, Any] = {}
            if run_id:
                meta["run_id"] = run_id
            if run_parent_id:
                meta["parent_run_id"] = str(run_parent_id)
            if isinstance(run_patch, dict) and run_patch:
                meta["patch"] = run_patch
            if run_strategy:
                meta["derive_strategy"] = run_strategy
            return meta

        def _emit_start() -> None:
            if on_tool_event and call_id and tool_name:
                on_tool_event({
                    "type": "tool_start",
                    "call_id": str(call_id),
                    "tool": str(tool_name),
                    "params": {
                        k: v for k, v in parsed_args.items() if not str(k).startswith("_")
                    },
                    **_run_meta(),
                })

        def _store(content: str, *, run_status: str | None = None) -> None:
            if not call_id:
                return
            results_by_id[call_id] = {
                "role": "tool",
                "tool_call_id": call_id,
                "content": content,
            }
            if on_tool_event and tool_name:
                end_meta = _run_meta()
                if run_status:
                    end_meta["run_status"] = run_status
                on_tool_event({
                    "type": "tool_end",
                    "call_id": str(call_id),
                    "tool": str(tool_name),
                    "params": {
                        k: v for k, v in parsed_args.items() if not str(k).startswith("_")
                    },
                    "content": content,
                    **end_meta,
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

        if run_registry is not None and run_id and run_registry.should_cancel_run(run_id):
            run_registry.finalize_cancelled(run_id)
            if call_id:
                _store("Error: Run cancelled by user", run_status="cancelled")
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
        from subagent.inject import inject_subagent_dispatch_args

        dispatch_args = inject_subagent_dispatch_args(
            tool_name,
            dispatch_args,
            analysis_context=analysis_context,
            permission=permission,
            hooks=hooks,
            llm_router=llm_router,
            filter_context=filter_context,
            loaded_skills=loaded_skills,
            loaded_references=loaded_references,
            on_tool_event=on_tool_event,
            run_registry=run_registry,
            job_id=job_id,
            parent_mode=(
                permission.mode.value
                if permission is not None and hasattr(permission.mode, "value")
                else str(getattr(permission, "mode", "analyze"))
            ),
        )
        if tool_name == "load_skill" and loaded_skills is not None:
            dispatch_args = {**dispatch_args, "_loaded_skills": loaded_skills}
        if tool_name == "load_reference" and loaded_references is not None:
            dispatch_args = {**dispatch_args, "_loaded_references": loaded_references}

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
                if run_registry is not None and run_id and run_registry.should_cancel_run(run_id):
                    raise RuntimeError("Run cancelled")
                tool_result = TOOL_DISPATCHER[tool_name](**dispatch_args)
            except RuntimeError as exc:
                if "cancel" in str(exc).lower() and run_registry is not None and run_id:
                    run_registry.finalize_cancelled(run_id)
                    end_tool_span(lf_span, output=str(exc), is_error=True)
                    if call_id:
                        _store(f"Error: {exc}", run_status="cancelled")
                    continue
                raise
            except Exception:
                _log.exception(
                    "tool_exec_failed tool=%s tool_call_id=%s",
                    tool_name,
                    call_id,
                )
                tool_result = f"Error: Tool {tool_name} execution failed"
                end_tool_span(lf_span, output=tool_result, is_error=True)
                if run_registry is not None and run_id:
                    run_registry.fail_run(run_id, tool_result)
                if call_id:
                    _store(
                        prepend_hook_messages(
                            tool_result,
                            pre_messages,
                        ),
                        run_status="failed",
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
                filter_context=filter_context,
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
            run_id=run_id,
            result_preview=truncate_for_log(tool_result),
        )
        if run_registry is not None and run_id:
            if isinstance(tool_result, str) and tool_result.strip().startswith("Error:"):
                run_registry.fail_run(run_id, tool_result)
                run_status = "failed"
            else:
                result_ref, dataset_id = extract_run_meta_from_result(
                    tool_result if isinstance(tool_result, str) else str(tool_result)
                )
                run_registry.complete_run(
                    run_id,
                    result_ref=result_ref,
                    dataset_id=dataset_id,
                )
                run_status = "completed"
        else:
            run_status = None
        if call_id:
            _store(tool_result, run_status=run_status)

    tool_results: list[dict[str, Any]] = []
    for call in tool_calls:
        call_id = call.get("id")
        if call_id and call_id in results_by_id:
            tool_results.append(results_by_id[call_id])
    return tool_results

import runtime_bootstrap  # noqa: F401

import json
import logging
from collections import deque
from typing import Any, Dict, List, Callable

from common.langfuse_tracing import agent_turn_span, record_loop_end
from common.llm_client import LLMClient
from common.logger import get_logger, log_event, truncate_for_log
from common.message import coerce_tool_calls_for_api, normalize_message
from common.system_prompt import SystemPromptBuilder, SystemPromptContext
from context import (
    DEFAULT_CONFIG,
    compact_history,
    estimate_context_size,
    micro_compact_messages,
)
from context.macro_compact import extract_tail_messages
from hooks import HookManager
from permission import PermissionManager, filter_tools
from cancel import TurnCancelled
from loop_state import LoopState
from recovery import DEFAULT_RECOVERY_CONFIG, RecoveryHandler
from skills import SkillRegistry, get_registry
from skills.message_meta import attach_pin_meta, pin_meta_for_tool
from skills.produce_bootstrap import (
    append_produce_report_writing_bootstrap,
    append_report_reference_bootstrap,
)
from skills.registry import _resolve_skill_name
from runs.modify_bootstrap import build_modify_bootstrap_call
from tools import TOOLS, execute_tool_calls
from permission.modes import CapabilityMode
from tools.runtime.pipeline.preprocess import dedupe_tool_calls, parse_args
from session.turns import resolve_loop_turn_count
from tools.handlers.compact import format_compact_applied_result
from tools.handlers.todo_write import (
    export_todo_snapshot,
    get_todo_reminder,
    mark_round_without_todo_update,
)
from hints.plan_checks import append_data_tool_checks
from hints.report_checks import append_report_write_checks

_log = get_logger("loop")

MAX_TOKENS = 8192
TOOL_LOOP_WINDOW = 6
_CONSULT_LIST_LOOP_WINDOW = 4
_TODO_ONLY_LOOP_WINDOW = 4
_LOOPING_TOOLS = frozenset({"inspect_schema", "load_skill"})
_PRODUCTIVE_DATA_TOOLS = frozenset({"query_data", "aggregate_data"})
ERROR_LOOP_WINDOW = 4
_AGGREGATE_INPUT_ERROR_MARKERS = (
    "aggregate_data 需要 input",
    "input is required",
)


# AgentLoop 声明周期（loop层级）
# request -> 预算检查 ->  compact -> LLM Call -> 响应构建

class AgentLoop:
    def __init__(
        self,
        loop_state: LoopState,
        llm_client: LLMClient | None = None,
        compact_config=DEFAULT_CONFIG,
        permission: PermissionManager | None = None,
        hooks: HookManager | None = None,
        recovery_config=DEFAULT_RECOVERY_CONFIG,
        progress_callback: Callable[[dict[str, Any]], None] | None = None,
        should_cancel: Callable[[], bool] | None = None,
        run_registry: Any | None = None,
        job_id: str | None = None,
    ):
        self.llm_client = llm_client or LLMClient()
        self.loop_state = loop_state or LoopState(messages=[])
        self.compact_config = compact_config
        self.permission = permission or loop_state.permission or PermissionManager()
        self.hooks = hooks if hooks is not None else loop_state.hooks
        self._prompt_builder = SystemPromptBuilder()
        self._recovery = RecoveryHandler(
            self.llm_client,
            config=recovery_config,
            state=self.loop_state.recovery,
        )
        self._recent_tool_batches: deque[tuple[str, ...]] = deque(maxlen=TOOL_LOOP_WINDOW)
        self._recent_consult_list_signatures: deque[tuple[str, ...]] = deque(
            maxlen=_CONSULT_LIST_LOOP_WINDOW
        )
        self._recent_todo_only_batches: deque[bool] = deque(maxlen=_TODO_ONLY_LOOP_WINDOW)
        self._recent_tool_error_signatures: deque[tuple[str, ...]] = deque(maxlen=ERROR_LOOP_WINDOW)
        self._recent_aggregate_input_errors: deque[bool] = deque(maxlen=ERROR_LOOP_WINDOW)
        self._progress_callback = progress_callback
        self._should_cancel = should_cancel
        self._run_registry = run_registry
        self._job_id = job_id

    def _check_cancelled(self) -> None:
        if self._should_cancel is not None and self._should_cancel():
            raise TurnCancelled()

    def _emit_progress(self, event: dict[str, Any]) -> None:
        if self._progress_callback is not None:
            try:
                self._progress_callback(event)
            except Exception:
                _log.exception("progress_callback_failed")

    def _system_prompt(self) -> str:
        registry = self.loop_state.skills or get_registry()
        todo_items, _rounds = export_todo_snapshot()
        return self._prompt_builder.build(
            SystemPromptContext(
                permission_mode=self.permission.mode.value,
                session_context=list(self.loop_state.session_context),
                filter_context=self.loop_state.filter_context,
                skills=registry,
                loaded_skills=set(self.loop_state.loaded_skills),
                loaded_references=set(self.loop_state.loaded_references),
                todo_items=todo_items,
                session_id=self.loop_state.session_id,
                modify_context=self.loop_state.modify_context,
            )
        )

    def _apply_pre_turn_compaction(self) -> None:
        # 每轮自动压缩context
        if not self.compact_config.enabled:
            return
        micro_compact_messages(self.loop_state.messages, config=self.compact_config)
        if estimate_context_size(self.loop_state.messages) <= self.compact_config.context_limit:
            return
        self.loop_state.messages = compact_history(
            self.loop_state.messages,
            self.llm_client,
            self.loop_state.compact,
            config=self.compact_config,
            reason="auto",
        )

    def _apply_manual_compaction(self, focus: str | None) -> dict[str, Any]:
        if not self.compact_config.enabled:
            return {"applied": False, "reason": "compaction_disabled"}
        messages = self.loop_state.messages
        before_count = len(messages)
        tail = extract_tail_messages(messages, config=self.compact_config)
        self.loop_state.messages = compact_history(
            messages,
            self.llm_client,
            self.loop_state.compact,
            focus=focus,
            config=self.compact_config,
            reason="manual",
        )
        return {
            "applied": True,
            "messages_before": before_count,
            "messages_after": len(self.loop_state.messages),
            "tail_turns": len(tail),
            "focus": focus,
            "recent_files": list(self.loop_state.compact.recent_files),
        }

    def _patch_compact_tool_results(
        self,
        tool_results: list[dict[str, Any]],
        compact_calls: list[dict[str, Any]],
        stats: dict[str, Any],
    ) -> None:
        compact_ids = {c.get("id") for c in compact_calls if c.get("id")}
        content = format_compact_applied_result(
            applied=bool(stats.get("applied")),
            messages_before=int(stats.get("messages_before") or 0),
            messages_after=int(stats.get("messages_after") or 0),
            tail_turns=int(stats.get("tail_turns") or 0),
            focus=stats.get("focus"),
            recent_files=stats.get("recent_files"),
            reason=stats.get("reason"),
        )
        for result in tool_results:
            if result.get("tool_call_id") in compact_ids:
                result["content"] = content
                break

    def _apply_recovery_compaction(self) -> None:
        if not self.compact_config.enabled:
            return
        self.loop_state.messages = compact_history(
            self.loop_state.messages,
            self.llm_client,
            self.loop_state.compact,
            config=self.compact_config,
            reason="recovery",
        )

    def run_turn(self):
        with agent_turn_span(turn=self.loop_state.turn_count):
            return self._run_turn_body()

    def _try_modify_bootstrap(self) -> bool:
        ctx = self.loop_state.modify_context
        if not ctx or ctx.get("_bootstrapped") or self._run_registry is None:
            return False

        built = build_modify_bootstrap_call(ctx, run_registry=self._run_registry)
        if built is None:
            return False

        tool_calls, hint = built
        self.loop_state.messages.append({
            "role": "assistant",
            "content": hint,
            "tool_calls": coerce_tool_calls_for_api(tool_calls),
        })
        if hint.strip():
            self._emit_progress({"type": "thinking", "content": hint})

        log_event(
            _log,
            logging.INFO,
            "modify_bootstrap_begin",
            count=len(tool_calls),
            names=[c.get("name") for c in tool_calls],
        )
        self._check_cancelled()
        tool_results = execute_tool_calls(
            tool_calls,
            compact_state=self.loop_state.compact,
            permission=self.permission,
            hooks=self.hooks,
            analysis_context=self.loop_state.analysis_context,
            loaded_skills=self.loop_state.loaded_skills,
            loaded_references=self.loop_state.loaded_references,
            llm_client=self.llm_client,
            filter_context=self.loop_state.filter_context,
            on_tool_event=self._emit_progress,
            run_registry=self._run_registry,
            job_id=self._job_id,
            modify_context=self.loop_state.modify_context,
        )
        self._check_cancelled()
        if not tool_results:
            return False

        append_data_tool_checks(tool_calls, tool_results)
        append_report_write_checks(tool_calls, tool_results)
        synced = _sync_tool_results_to_messages(
            self.loop_state.messages,
            tool_calls,
            tool_results,
        )
        self.loop_state.messages_count += (1 + synced)
        self.loop_state.turn_count += 1
        self.loop_state.continue_reason = "modify_bootstrap_executed"
        log_event(
            _log,
            logging.INFO,
            "modify_bootstrap_done",
            synced=synced,
            next_turn=self.loop_state.turn_count,
        )
        return True

    def _run_turn_body(self):
        self._check_cancelled()
        if self._try_modify_bootstrap():
            return True
        registry = self.loop_state.skills or get_registry()
        if self.permission.mode == CapabilityMode.PRODUCE:
            append_produce_report_writing_bootstrap(
                self.loop_state.messages,
                self.loop_state.loaded_skills,
                registry,
            )
        if "report-writing" in self.loop_state.loaded_skills:
            append_report_reference_bootstrap(
                self.loop_state.messages,
                self.loop_state.loaded_references,
                user_message=self.loop_state.analysis_context.current_user_message,
                filter_context=self.loop_state.filter_context,
                loaded_skills=self.loop_state.loaded_skills,
            )
        self._apply_pre_turn_compaction()

        log_event(
            _log,
            logging.INFO,
            "turn_begin",
            turn=self.loop_state.turn_count,
            messages=len(self.loop_state.messages),
        )
        self._emit_progress({"type": "llm_start"})

        on_content_delta = None
        if self._progress_callback is not None:
            def on_content_delta(delta: str) -> None:
                self._check_cancelled()
                if delta:
                    self._emit_progress({"type": "thinking_delta", "delta": delta})

        visible_tools = filter_tools(TOOLS, self.permission.mode)
        raw_response, failure_reason = self._recovery.request_completion(
            system_prompt=self._system_prompt(),
            messages=self.loop_state.messages,
            tools=visible_tools,
            max_tokens=MAX_TOKENS,
            normalize_fn=normalize_message,
            compact_fn=self._apply_recovery_compaction,
            on_content_delta=on_content_delta,
        )
        self._check_cancelled()
        if not raw_response or not getattr(raw_response, "choices", None):
            self.loop_state.continue_reason = failure_reason or "llm_no_response"
            log_event(
                _log,
                logging.WARNING,
                "llm_no_response",
                turn=self.loop_state.turn_count,
                recovery_reason=failure_reason,
            )
            self.loop_state.messages.append({
                "role": "assistant",
                "content": _recovery_failure_message(failure_reason),
            })
            return False
        response = raw_response.choices[0]

        # 将LLM的响应添加到 messages（Assistant）；截断续写时 handler 可能已追加一条 assistant
        if self.loop_state.messages and self.loop_state.messages[-1].get("role") == "assistant":
            assistant_message = self.loop_state.messages[-1]
        else:
            assistant_message = {
                "role": "assistant",
                "content": response.message.content or "",
            }
            self.loop_state.messages.append(assistant_message)

        tool_calls: list[dict[str, Any]] = []
        if getattr(response.message, "tool_calls", None):
            tool_calls = dedupe_tool_calls(
                self.llm_client.extract_tool_calls(raw_response)
            )
            assistant_message["tool_calls"] = coerce_tool_calls_for_api(tool_calls)
            if not assistant_message["tool_calls"]:
                assistant_message["tool_calls"] = coerce_tool_calls_for_api(
                    response.message.tool_calls
                )
            thinking_text = (assistant_message.get("content") or "").strip()
            if thinking_text:
                self._emit_progress({"type": "thinking", "content": thinking_text})
            elif not (assistant_message.get("content") or "").strip():
                assistant_message["content"] = None
        elif response.message.content:
            assistant_message["content"] = response.message.content

        # 如果LLM没有工具调用，则结束循环
        if response.finish_reason != "tool_calls":
            self.loop_state.continue_reason = None
            preview = truncate_for_log(response.message.content or "")
            if response.message.content:
                answer_event: dict[str, Any] = {
                    "type": "answer",
                    "content": response.message.content,
                }
                if self.loop_state.turn_count == 0:
                    answer_event["clear_thinking"] = True
                self._emit_progress(answer_event)
            log_event(
                _log,
                logging.INFO,
                "turn_end",
                reason="no_tool_calls",
                finish_reason=response.finish_reason,
                assistant_preview=preview,
            )
            return False

        # 如果LLM有工具调用，则执行工具调用（tool_calls 已在上方 dedupe 并写入 assistant）
        if self._should_break_tool_loop(tool_calls):
            self.loop_state.continue_reason = "tool_loop_guard"
            guard_hint = (
                "检测到工具调用在 inspect_schema/load_skill 上反复循环，已自动停止本轮。"
                "若你要做统计（计数/均值/分组），请切换到 /mode analyze 并使用 "
                "query_data / aggregate_data。"
            )
            _sync_tool_results_to_messages(
                self.loop_state.messages,
                tool_calls,
                missing_content="Cancelled: tool loop guard",
            )
            self.loop_state.messages.append({"role": "assistant", "content": guard_hint})
            log_event(
                _log,
                logging.WARNING,
                "tool_loop_guard_triggered",
                turn=self.loop_state.turn_count,
                mode=self.permission.mode.value,
                batches=list(self._recent_tool_batches),
            )
            return False
        if self._should_break_consult_list_loop(tool_calls):
            self.loop_state.continue_reason = "consult_list_loop_guard"
            guard_hint = (
                "检测到 consult 模式下对同一路径反复 list_files，已自动停止本轮。"
                "列目录不能读取 CSV 内容，也不能做统计。请切换到 /mode analyze，"
                "再用 inspect_schema(resource=submit_record, class=Class1) 或 query_data。"
            )
            _sync_tool_results_to_messages(
                self.loop_state.messages,
                tool_calls,
                missing_content="Cancelled: consult list loop guard",
            )
            self.loop_state.messages.append({"role": "assistant", "content": guard_hint})
            log_event(
                _log,
                logging.WARNING,
                "consult_list_loop_guard_triggered",
                turn=self.loop_state.turn_count,
                mode=self.permission.mode.value,
                signatures=list(self._recent_consult_list_signatures),
            )
            return False
        if self._should_break_todo_only_loop(tool_calls):
            self.loop_state.continue_reason = "todo_only_loop_guard"
            guard_hint = (
                "检测到连续多轮仅更新 todo_write 而无数据分析，已自动停止本轮。"
                "若已有明确查询目标，请直接 query_data / aggregate_data；"
                "多步任务也应在 todo 之外调用 inspect_schema 等工具。"
            )
            _sync_tool_results_to_messages(
                self.loop_state.messages,
                tool_calls,
                missing_content="Cancelled: todo-only loop guard",
            )
            self.loop_state.messages.append({"role": "assistant", "content": guard_hint})
            log_event(
                _log,
                logging.WARNING,
                "todo_only_loop_guard_triggered",
                turn=self.loop_state.turn_count,
                mode=self.permission.mode.value,
            )
            return False
        log_event(
            _log,
            logging.INFO,
            "tool_batch_begin",
            count=len(tool_calls),
            names=[c.get("name") for c in tool_calls],
            args_preview=self._tool_args_preview(tool_calls),
        )
        self._check_cancelled()
        tool_results = execute_tool_calls(
            tool_calls,
            compact_state=self.loop_state.compact,
            permission=self.permission,
            hooks=self.hooks,
            analysis_context=self.loop_state.analysis_context,
            loaded_skills=self.loop_state.loaded_skills,
            loaded_references=self.loop_state.loaded_references,
            llm_client=self.llm_client,
            filter_context=self.loop_state.filter_context,
            on_tool_event=self._emit_progress,
            run_registry=self._run_registry,
            job_id=self._job_id,
            modify_context=self.loop_state.modify_context,
        )
        self._check_cancelled()

        # 错误响应防护
        if self._should_break_error_loop(tool_calls, tool_results):
            self.loop_state.continue_reason = "tool_error_loop_guard"
            guard_hint = (
                "检测到工具调用连续报错并重复，已自动停止本轮，避免空转。"
                "请检查工具参数：aggregate_data 需要 input/result_ref；"
                "如为统计问题，先 query_data 再 aggregate_data。"
            )
            _sync_tool_results_to_messages(
                self.loop_state.messages,
                tool_calls,
                tool_results,
            )
            self.loop_state.messages.append({"role": "assistant", "content": guard_hint})
            log_event(
                _log,
                logging.WARNING,
                "tool_error_loop_guard_triggered",
                turn=self.loop_state.turn_count,
                mode=self.permission.mode.value,
                error_signatures=list(self._recent_tool_error_signatures),
            )
            return False

        compact_calls = [c for c in tool_calls if c.get("name") == "compact"]
        compact_focus = None
        if compact_calls:
            args = compact_calls[0].get("arguments") or {}
            if isinstance(args, str):
                try:
                    args = json.loads(args) if args else {}
                except (TypeError, ValueError):
                    args = {}
            compact_focus = args.get("focus") if isinstance(args, dict) else None

        # 处理 todo_write 工具调用
        has_todo_write_call = any(c.get("name") == "todo_write" for c in tool_calls)
        if not has_todo_write_call:
            mark_round_without_todo_update()
        else:
            reminder = get_todo_reminder()
            if reminder:
                todo_call_ids = {
                    c.get("id")
                    for c in tool_calls
                    if c.get("name") == "todo_write" and c.get("id")
                }
                for result in tool_results:
                    if result.get("tool_call_id") in todo_call_ids:
                        original = result.get("content") or ""
                        result["content"] = f"{original}\n\n{reminder}".strip()
                        break
        
        append_data_tool_checks(tool_calls, tool_results)
        append_report_write_checks(tool_calls, tool_results)

        if not tool_results:
            # 工具调用失败
            self.loop_state.continue_reason = "tool_calls_failed"
            _sync_tool_results_to_messages(
                self.loop_state.messages,
                tool_calls,
                missing_content="Cancelled: tool execution returned no results",
            )
            log_event(_log, logging.WARNING, "tool_batch_empty", turn=self.loop_state.turn_count)
            return False

        if compact_calls and not self.compact_config.enabled:
            self._patch_compact_tool_results(
                tool_results,
                compact_calls,
                {"applied": False, "reason": "compaction_disabled"},
            )

        # 将工具调用结果添加到 messages 中（Tool），缺失 id 补占位以满足 OpenAI 协议
        synced = _sync_tool_results_to_messages(
            self.loop_state.messages, tool_calls, tool_results
        )
        if compact_calls and self.compact_config.enabled:
            compact_stats = self._apply_manual_compaction(compact_focus)
            self._patch_compact_tool_results(tool_results, compact_calls, compact_stats)
            for msg in self.loop_state.messages:
                if msg.get("role") != "tool":
                    continue
                for result in tool_results:
                    if result.get("tool_call_id") == msg.get("tool_call_id"):
                        msg["content"] = result["content"]
                        break

        self.loop_state.messages_count += (1 + synced)
        self.loop_state.turn_count += 1
        self.loop_state.continue_reason = "tool_calls_executed"
        log_event(
            _log,
            logging.INFO,
            "turn_end",
            reason="tool_calls_executed",
            tools=len(tool_results),
            next_turn=self.loop_state.turn_count,
        )
        return True

    def _should_break_tool_loop(self, tool_calls: list[dict[str, Any]]) -> bool:
        names = tuple(sorted(str(c.get("name") or "") for c in tool_calls if c.get("name")))
        if not names:
            self._recent_tool_batches.clear()
            return False

        name_set = set(names)
        if name_set & _PRODUCTIVE_DATA_TOOLS:
            self._recent_tool_batches.clear()
            return False

        if name_set.issubset(_LOOPING_TOOLS):
            self._recent_tool_batches.append(names)
        else:
            self._recent_tool_batches.clear()
            return False

        if len(self._recent_tool_batches) < TOOL_LOOP_WINDOW:
            return False

        # Break only when all recent batches are low-value inspection loops.
        return all(set(batch).issubset(_LOOPING_TOOLS) for batch in self._recent_tool_batches)

    def _list_files_batch_signature(self, tool_calls: list[dict[str, Any]]) -> tuple[str, ...] | None:
        paths: list[str] = []
        for call in tool_calls:
            if call.get("name") != "list_files":
                return None
            args = parse_args(call.get("arguments", {}))
            raw_path = args.get("path")
            paths.append(str(raw_path).strip() if raw_path is not None else ".")
        return tuple(sorted(paths))

    def _should_break_consult_list_loop(self, tool_calls: list[dict[str, Any]]) -> bool:
        if self.permission.mode is not CapabilityMode.CONSULT:
            self._recent_consult_list_signatures.clear()
            return False

        signature = self._list_files_batch_signature(tool_calls)
        if signature is None:
            self._recent_consult_list_signatures.clear()
            return False

        self._recent_consult_list_signatures.append(signature)
        if len(self._recent_consult_list_signatures) < _CONSULT_LIST_LOOP_WINDOW:
            return False

        first = self._recent_consult_list_signatures[0]
        return all(sig == first for sig in self._recent_consult_list_signatures)

    def _should_break_todo_only_loop(self, tool_calls: list[dict[str, Any]]) -> bool:
        names = {str(c.get("name") or "") for c in tool_calls if c.get("name")}
        if names != {"todo_write"}:
            self._recent_todo_only_batches.clear()
            return False
        if names & _PRODUCTIVE_DATA_TOOLS:
            self._recent_todo_only_batches.clear()
            return False
        self._recent_todo_only_batches.append(True)
        if len(self._recent_todo_only_batches) < _TODO_ONLY_LOOP_WINDOW:
            return False
        return True

    def _tool_args_preview(self, tool_calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
        preview: list[dict[str, Any]] = []
        for call in tool_calls:
            raw_args = call.get("arguments", {})
            args = raw_args
            if isinstance(raw_args, str):
                try:
                    args = json.loads(raw_args) if raw_args else {}
                except (TypeError, ValueError):
                    args = {"_raw": truncate_for_log(raw_args, max_len=200)}
            if not isinstance(args, dict):
                args = {"_value": str(args)}
            preview.append(
                {
                    "name": call.get("name"),
                    "id": call.get("id"),
                    "args": {
                        k: (truncate_for_log(str(v), max_len=120) if isinstance(v, str) else v)
                        for k, v in args.items()
                    },
                }
            )
        return preview

    def _should_break_error_loop(
        self,
        tool_calls: list[dict[str, Any]],
        tool_results: list[dict[str, Any]],
    ) -> bool:
        if not tool_calls or not tool_results:
            self._recent_tool_error_signatures.clear()
            self._recent_aggregate_input_errors.clear()
            return False

        if self._should_break_aggregate_input_loop(tool_calls, tool_results):
            return True

        by_call_id = {c.get("id"): c.get("name") for c in tool_calls if c.get("id")}
        signature_parts: list[str] = []
        all_error = True
        for result in tool_results:
            content = result.get("content") or ""
            if not isinstance(content, str) or not content.startswith("Error:"):
                all_error = False
                break
            tool_name = by_call_id.get(result.get("tool_call_id"), "unknown")
            short_err = truncate_for_log(content, max_len=120)
            signature_parts.append(f"{tool_name}:{short_err}")

        if not all_error or not signature_parts:
            self._recent_tool_error_signatures.clear()
            return False

        signature = tuple(sorted(signature_parts))
        self._recent_tool_error_signatures.append(signature)
        if len(self._recent_tool_error_signatures) < ERROR_LOOP_WINDOW:
            return False
        return all(s == signature for s in self._recent_tool_error_signatures)

    def _should_break_aggregate_input_loop(
        self,
        tool_calls: list[dict[str, Any]],
        tool_results: list[dict[str, Any]],
    ) -> bool:
        """Stop when aggregate_data keeps failing for missing input (even if query_data succeeds)."""
        by_call_id = {c.get("id"): c.get("name") for c in tool_calls if c.get("id")}
        had_aggregate_input_error = False
        for result in tool_results:
            tool_name = by_call_id.get(result.get("tool_call_id"), "")
            if tool_name != "aggregate_data":
                continue
            content = result.get("content") or ""
            if not isinstance(content, str):
                continue
            if any(marker in content for marker in _AGGREGATE_INPUT_ERROR_MARKERS):
                had_aggregate_input_error = True
                break

        if had_aggregate_input_error:
            self._recent_aggregate_input_errors.append(True)
        else:
            self._recent_aggregate_input_errors.clear()

        if len(self._recent_aggregate_input_errors) < ERROR_LOOP_WINDOW:
            return False
        return all(self._recent_aggregate_input_errors)

    def _align_turn_count_for_user_round(self) -> None:
        """Continue turn index after restart / new user message (not reset to 1)."""
        self.loop_state.turn_count = resolve_loop_turn_count(
            self.loop_state.messages,
            stored_user_turn_count=self.loop_state.turn_count,
        )

    def run_loop(self):
        self._align_turn_count_for_user_round()
        log_event(
            _log,
            logging.INFO,
            "loop_begin",
            turn=self.loop_state.turn_count,
        )
        while True:
            self._check_cancelled()
            if not self.run_turn():
                break
        record_loop_end(
            continue_reason=self.loop_state.continue_reason,
            turn_count=self.loop_state.turn_count,
        )
        log_event(
            _log,
            logging.INFO,
            "loop_end",
            continue_reason=self.loop_state.continue_reason,
            turn=self.loop_state.turn_count,
            messages=len(self.loop_state.messages),
        )


def _resource_id_for_tool_call(tool_name: str, call: dict[str, Any]) -> str:
    args = call.get("arguments") or {}
    if isinstance(args, str):
        try:
            args = json.loads(args) if args.strip() else {}
        except (TypeError, ValueError):
            args = {}
    if not isinstance(args, dict):
        args = {}
    if tool_name == "load_skill":
        return _resolve_skill_name(str(args.get("name") or ""))
    if tool_name == "load_reference":
        return str(args.get("name") or "").strip()
    return ""


def _sync_tool_results_to_messages(
    messages: list[dict[str, Any]],
    tool_calls: list[dict[str, Any]],
    tool_results: list[dict[str, Any]] | None = None,
    *,
    missing_content: str = (
        "[Tool result missing; call was deduplicated or not executed.]"
    ),
) -> int:
    """Append one tool message per call id; use placeholders when results are absent."""
    results_by_id = {
        str(r["tool_call_id"]): r
        for r in (tool_results or [])
        if r.get("tool_call_id")
    }
    appended = 0
    for call in tool_calls:
        call_id = call.get("id")
        if not call_id:
            continue
        call_id = str(call_id)
        fn = call.get("function") or {}
        tool_name = str(call.get("name") or fn.get("name") or "")
        if call_id in results_by_id:
            msg = dict(results_by_id[call_id])
            content = str(msg.get("content") or "")
            base_meta = pin_meta_for_tool(tool_name, content)
            if base_meta:
                kind = base_meta["content_kind"]
                resource_id = _resource_id_for_tool_call(tool_name, call) or content[:80]
                msg = attach_pin_meta(
                    msg,
                    content_kind=kind,
                    resource_id=resource_id,
                )
            messages.append(msg)
        else:
            messages.append({
                "role": "tool",
                "tool_call_id": call_id,
                "content": missing_content,
            })
        appended += 1
    return appended


def _recovery_failure_message(reason: str | None) -> str:
    if reason == "output_truncated_exhausted":
        return (
            "LLM 输出多次达到长度上限，已无法自动续写。"
            "请缩小任务范围、要求分步输出，或使用 compact 压缩上下文后重试。"
        )
    if reason == "context_overflow_exhausted":
        return (
            "LLM 上下文过长，自动压缩后仍无法完成调用。"
            "请使用 compact 工具或开启新会话后重试。"
        )
    if reason == "transient_error_exhausted":
        return "LLM 调用因网络或限流多次失败，请稍后重试。"
    return "LLM 调用失败：未返回有效响应（请检查 API Key、模型配置或网络连接）。"
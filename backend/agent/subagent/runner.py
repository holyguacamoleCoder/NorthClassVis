"""Run an isolated tool-calling loop for a delegated sub-task."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Callable

from common.llm_router import LLMRouter
from common.logger import get_logger, log_event
from common.message import (
    attach_reasoning_from_sdk,
    coerce_tool_calls_for_api,
    normalize_message,
)
from hooks import HookManager
from loop_state import AnalysisToolContext
from permission import PermissionManager
from permission.modes import CapabilityMode
from recovery import RecoveryHandler

from .kinds import SubAgentKind, filter_subagent_tools, kind_config, resolve_kind
from .prompts import build_subagent_system_prompt

_log = get_logger("subagent")

ProgressCallback = Callable[[dict[str, Any]], None] | None


@dataclass
class SubAgentParentContext:
    session_id: str | None = None
    user_turn: int = 0
    parent_mode: str = "analyze"
    filter_context: Any | None = None
    visual_links: list[dict[str, Any]] = field(default_factory=list)
    loaded_skills: set[str] = field(default_factory=set)
    loaded_references: set[str] = field(default_factory=set)
    analysis_context: AnalysisToolContext | None = None


@dataclass
class SubAgentResult:
    ok: bool
    kind: str
    summary: str
    turns: int = 0
    refs: list[str] = field(default_factory=list)
    dataset_ids: list[str] = field(default_factory=list)
    error: str | None = None

    def format_tool_result(self) -> str:
        lines = [
            f"[SubAgent {self.kind} {'OK' if self.ok else 'FAIL'}]",
            f"turns: {self.turns}",
        ]
        if self.refs:
            lines.append("refs:")
            for ref in self.refs[:12]:
                lines.append(f"  - {ref}")
            if len(self.refs) > 12:
                lines.append(f"  … +{len(self.refs) - 12} more")
        if self.dataset_ids:
            lines.append("dataset_ids:")
            for ds in self.dataset_ids[:8]:
                lines.append(f"  - {ds}")
        lines.append("summary:")
        lines.append(self.summary.strip() or "(empty)")
        if self.error:
            lines.append(f"error: {self.error}")
        return "\n".join(lines)


class SubAgentRunner:
    """Bounded inner loop; does not mutate parent messages."""

    def __init__(
        self,
        *,
        llm_router: LLMRouter,
        permission: PermissionManager | None = None,
        hooks: HookManager | None = None,
        progress_callback: ProgressCallback = None,
        run_registry: Any | None = None,
        job_id: str | None = None,
    ):
        self.llm_router = llm_router
        self.permission = permission or PermissionManager()
        self.hooks = hooks or HookManager()
        self._progress = progress_callback
        self._run_registry = run_registry
        self._job_id = job_id

    def run(
        self,
        kind_raw: str,
        task: str,
        *,
        parent: SubAgentParentContext | None = None,
    ) -> SubAgentResult:
        kind = resolve_kind(kind_raw)
        if kind is None:
            return SubAgentResult(
                ok=False,
                kind=str(kind_raw or ""),
                summary="",
                error=f"unknown subagent kind {kind_raw!r}; use data_analyst|report_writer|report_reviewer",
            )
        cfg = kind_config(kind)
        task_text = (task or "").strip()
        if not task_text:
            return SubAgentResult(
                ok=False,
                kind=kind.value,
                summary="",
                error="task is required",
            )

        from tools import TOOLS, execute_tool_calls
        from tools.runtime.pipeline.preprocess import dedupe_tool_calls

        parent = parent or SubAgentParentContext()
        self._emit({
            "type": "subagent_start",
            "kind": kind.value,
            "task_preview": task_text[:240],
        })

        if parent.analysis_context is not None:
            analysis_context = parent.analysis_context
            analysis_context.current_user_message = task_text
        else:
            analysis_context = AnalysisToolContext(
                session_id=parent.session_id,
                user_turn=parent.user_turn,
                current_user_message=task_text,
                session_visual_links=list(parent.visual_links),
            )

        sub_permission = PermissionManager(mode=cfg.capability_mode)
        llm_client = self.llm_router.main_for_mode(cfg.capability_mode)
        recovery = RecoveryHandler(llm_client)
        system_prompt = build_subagent_system_prompt(
            kind, parent_mode=parent.parent_mode
        )
        messages: list[dict[str, Any]] = [{"role": "user", "content": task_text}]
        tools = filter_subagent_tools(TOOLS, kind)
        final_text = ""
        turns = 0

        log_event(
            _log,
            logging.INFO,
            "subagent_begin",
            kind=kind.value,
            max_turns=cfg.max_turns,
            tools=len(tools),
        )

        try:
            for turn in range(cfg.max_turns):
                turns = turn + 1

                response, failure = recovery.request_completion(
                    system_prompt=system_prompt,
                    messages=messages,
                    tools=tools,
                    max_tokens=cfg.max_tokens,
                    normalize_fn=normalize_message,
                    compact_fn=lambda: None,
                )
                if not response or not getattr(response, "choices", None):
                    return self._finish(
                        kind,
                        ok=False,
                        summary=final_text,
                        turns=turns,
                        analysis_context=analysis_context,
                        error=failure or "llm_no_response",
                    )

                choice = response.choices[0]
                assistant: dict[str, Any] = {
                    "role": "assistant",
                    "content": getattr(choice.message, "content", None) or "",
                }
                attach_reasoning_from_sdk(assistant, choice.message)

                tool_calls: list[dict[str, Any]] = []
                if getattr(choice.message, "tool_calls", None):
                    tool_calls = dedupe_tool_calls(
                        [
                            {
                                "id": tc.id,
                                "name": (
                                    tc.function.name
                                    if hasattr(tc, "function")
                                    else getattr(tc, "name", "")
                                ),
                                "arguments": (
                                    tc.function.arguments
                                    if hasattr(tc, "function")
                                    else getattr(tc, "arguments", "{}")
                                ),
                            }
                            for tc in choice.message.tool_calls
                        ]
                    )
                    assistant["tool_calls"] = coerce_tool_calls_for_api(tool_calls)
                    if not (assistant.get("content") or "").strip():
                        assistant["content"] = None
                messages.append(assistant)

                if not tool_calls:
                    final_text = (assistant.get("content") or "").strip()
                    return self._finish(
                        kind,
                        ok=True,
                        summary=final_text,
                        turns=turns,
                        analysis_context=analysis_context,
                    )

                inner_progress = self._wrap_inner_tool_event(kind)
                tool_results = execute_tool_calls(
                    tool_calls,
                    compact_state=None,
                    permission=sub_permission,
                    hooks=self.hooks,
                    analysis_context=analysis_context,
                    loaded_skills=set(parent.loaded_skills),
                    loaded_references=set(parent.loaded_references),
                    llm_client=llm_client,
                    filter_context=parent.filter_context,
                    on_tool_event=inner_progress,
                    run_registry=self._run_registry,
                    job_id=self._job_id,
                )
                for result in tool_results:
                    messages.append({
                        "role": "tool",
                        "tool_call_id": result.get("tool_call_id"),
                        "content": result.get("content") or "",
                    })

            return self._finish(
                kind,
                ok=False,
                summary=final_text,
                turns=turns,
                analysis_context=analysis_context,
                error=f"max_turns ({cfg.max_turns}) exceeded",
            )
        except Exception as exc:
            _log.exception("subagent_failed kind=%s", kind.value)
            return self._finish(
                kind,
                ok=False,
                summary=final_text,
                turns=turns,
                analysis_context=analysis_context,
                error=str(exc),
            )

    def _finish(
        self,
        kind: SubAgentKind,
        *,
        ok: bool,
        summary: str,
        turns: int,
        analysis_context: AnalysisToolContext,
        error: str | None = None,
    ) -> SubAgentResult:
        refs, dataset_ids = _collect_refs(analysis_context)
        result = SubAgentResult(
            ok=ok,
            kind=kind.value,
            summary=summary,
            turns=turns,
            refs=refs,
            dataset_ids=dataset_ids,
            error=error,
        )
        self._emit({
            "type": "subagent_end",
            "kind": kind.value,
            "turns": turns,
            "status": "ok" if ok else "fail",
            "refs_count": len(refs),
        })
        log_event(
            _log,
            logging.INFO,
            "subagent_end",
            kind=kind.value,
            ok=ok,
            turns=turns,
            refs=len(refs),
            error=error,
        )
        return result

    def _wrap_inner_tool_event(
        self,
        kind: SubAgentKind,
    ) -> Callable[[dict[str, Any]], None] | None:
        if self._progress is None:
            return None

        def handler(event: dict[str, Any]) -> None:
            et = event.get("type")
            if et not in ("tool_start", "tool_end"):
                return
            mapped = "subagent_tool_start" if et == "tool_start" else "subagent_tool_end"
            self._emit({
                **event,
                "type": mapped,
                "subagent_kind": kind.value,
            })

        return handler

    def _emit(self, event: dict[str, Any]) -> None:
        if self._progress is None:
            return
        try:
            self._progress(event)
        except Exception:
            _log.exception("subagent_progress_failed")


def _collect_refs(
    analysis_context: AnalysisToolContext,
) -> tuple[list[str], list[str]]:
    refs: list[str] = []
    dataset_ids: list[str] = []
    seen_refs: set[str] = set()
    seen_ds: set[str] = set()

    for snap in analysis_context.turn_snapshots:
        if snap.result_ref and snap.result_ref not in seen_refs:
            seen_refs.add(snap.result_ref)
            refs.append(snap.result_ref)
        if snap.dataset_id and snap.dataset_id not in seen_ds:
            seen_ds.add(snap.dataset_id)
            dataset_ids.append(snap.dataset_id)

    if analysis_context.session_id:
        try:
            from data.dataset_registry import list_datasets

            for rec in list_datasets(analysis_context.session_id, tail=50):
                if rec.result_ref and rec.result_ref not in seen_refs:
                    seen_refs.add(rec.result_ref)
                    refs.append(rec.result_ref)
                if rec.dataset_id and rec.dataset_id not in seen_ds:
                    seen_ds.add(rec.dataset_id)
                    dataset_ids.append(rec.dataset_id)
        except Exception:
            pass

    return refs, dataset_ids

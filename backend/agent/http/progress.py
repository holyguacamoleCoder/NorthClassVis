"""Build incremental job progress events for HTTP polling."""

from __future__ import annotations

import time
from typing import Any, Callable

from .adapter import _reference_name_from_params, _skill_name_from_params, build_tool_step


ProgressCallback = Callable[[dict[str, Any]], None]


def make_job_progress_handler(
    update_fn: Callable[[dict[str, Any]], None],
    *,
    initial_loaded_skills: list[str] | None = None,
    initial_loaded_references: list[str] | None = None,
) -> ProgressCallback:
    """Return a callback AgentLoop / executor can invoke."""
    loaded_accum: set[str] = set(initial_loaded_skills or [])
    loaded_refs_accum: set[str] = set(initial_loaded_references or [])
    report_links_accum: list[dict[str, Any]] = []
    memory_saved_accum: list[dict[str, Any]] = []
    plan_state = {"sent": False}

    def handler(event: dict[str, Any]) -> None:
        et = event.get("type")
        patch: dict[str, Any] = {"updated_at": time.time()}

        if et == "llm_start":
            patch.update({"phase": "llm", "hint": "正在调用模型…", "running_tool": None})
        elif et == "tool_start":
            running: dict[str, Any] = {
                "call_id": event.get("call_id"),
                "tool": event.get("tool"),
                "params": event.get("params") or {},
            }
            for key in ("run_id", "parent_run_id", "patch", "derive_strategy"):
                if event.get(key) is not None:
                    running[key] = event.get(key)
            patch.update({
                "phase": "tools",
                "hint": f"正在执行 {event.get('tool', 'tool')}…",
                "running_tool": running,
            })
        elif et == "tool_end":
            tool_name = str(event.get("tool") or "unknown")
            params = event.get("params") if isinstance(event.get("params"), dict) else {}
            content = str(event.get("content") or "")
            step = build_tool_step(
                tool_name,
                params,
                content,
                call_id=str(event.get("call_id") or "") or None,
                run_id=str(event.get("run_id") or "") or None,
                parent_run_id=str(event.get("parent_run_id") or "") or None,
                patch=event.get("patch") if isinstance(event.get("patch"), dict) else None,
                derive_strategy=event.get("derive_strategy"),
                run_status=str(event.get("run_status") or "") or None,
            )
            patch.update({
                "phase": "tools",
                "hint": "工具执行完成，继续分析…",
                "running_tool": None,
                "append_step": step,
                "append_timeline": {"kind": "tool", "phase": "process", "step": step},
            })
            if tool_name == "todo_write":
                from tools.handlers.todo_write import export_todo_snapshot

                items, _rounds = export_todo_snapshot()
                patch["todo_items"] = items
            elif tool_name == "load_skill":
                skill_name = step.get("skill_name") or _skill_name_from_params(params)
                if skill_name and step.get("status") == "ok":
                    loaded_accum.add(skill_name)
                    patch["loaded_skills"] = sorted(loaded_accum)
            elif tool_name == "load_reference":
                ref_name = step.get("reference_name") or _reference_name_from_params(params)
                if ref_name and step.get("status") == "ok":
                    loaded_refs_accum.add(ref_name)
                    patch["loaded_references"] = sorted(loaded_refs_accum)
            elif tool_name in ("write_file", "edit_file") and step.get("status") == "ok":
                from ..report_delivery import report_link_from_tool

                link = report_link_from_tool(tool_name, content, params)
                if link:
                    paths = {item.get("path") for item in report_links_accum}
                    if link["path"] not in paths:
                        report_links_accum.append(link)
                    patch["report_links"] = list(report_links_accum)
            elif tool_name in ("memory", "save_memory") and step.get("status") == "ok":
                from ..memory_delivery import memory_event_from_tool

                event = memory_event_from_tool(tool_name, content, params)
                if event:
                    keys = {
                        (e.get("name"), e.get("target"), e.get("action"))
                        for e in memory_saved_accum
                    }
                    dedupe_key = (
                        event.get("name"),
                        event.get("target"),
                        event.get("action"),
                    )
                    if dedupe_key not in keys:
                        memory_saved_accum.append(event)
                    patch["memory_saved"] = list(memory_saved_accum)
        elif et == "answer":
            text = str(event.get("content") or "")
            patch.update({
                "phase": "answer",
                "hint": "正在整理回答…",
                "answer": text,
                "running_tool": None,
            })
            if text:
                patch["append_timeline"] = {
                    "kind": "narration",
                    "phase": "conclusion",
                    "text": text,
                }
            if event.get("clear_thinking"):
                patch["thinking"] = ""
        elif et == "thinking":
            text = str(event.get("content") or "")
            if not plan_state["sent"]:
                plan_state["sent"] = True
                patch.update({
                    "phase": "thinking",
                    "hint": "正在整理分析思路…",
                    "thinking": text,
                    "running_tool": None,
                })
                if text:
                    patch["append_timeline"] = {
                        "kind": "narration",
                        "phase": "plan",
                        "text": text,
                    }
            else:
                patch.update({
                    "phase": "thinking",
                    "hint": "正在继续分析…",
                    "running_tool": None,
                    "append_thinking_update": text,
                })
                if text:
                    patch["append_timeline"] = {
                        "kind": "narration",
                        "phase": "plan_update",
                        "text": text,
                    }
        elif et == "thinking_delta":
            patch.update({
                "phase": "thinking",
                "hint": "正在理解问题…",
                "append_thinking": str(event.get("delta") or ""),
                "running_tool": None,
            })
        elif et == "answer_delta":
            patch.update({
                "phase": "answer",
                "hint": "正在生成回答…",
                "append_answer": str(event.get("delta") or ""),
                "running_tool": None,
            })
        else:
            return

        update_fn(patch)

    return handler


def empty_job_progress(
    *,
    todo_items: list[dict[str, str]] | None = None,
    loaded_skills: list[str] | None = None,
    loaded_references: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "phase": "starting",
        "hint": "思考中…",
        "tool_steps": [],
        "timeline": [],
        "running_tool": None,
        "thinking": "",
        "answer": "",
        "todo_items": list(todo_items or []),
        "loaded_skills": list(loaded_skills or []),
        "loaded_references": list(loaded_references or []),
        "report_links": [],
        "memory_saved": [],
        "thinking_updates": [],
    }


def seed_job_progress_from_session(session: Any) -> dict[str, Any]:
    """Initialize job progress with persisted session plan / skills."""
    return empty_job_progress(
        todo_items=list(getattr(session, "todo_items", None) or []),
        loaded_skills=list(getattr(session, "loaded_skills", None) or []),
        loaded_references=list(getattr(session, "loaded_references", None) or []),
    )


def merge_progress_patch(progress: dict[str, Any], patch: dict[str, Any]) -> None:
    append = patch.pop("append_step", None)
    append_timeline = patch.pop("append_timeline", None)
    append_answer = patch.pop("append_answer", None)
    append_thinking = patch.pop("append_thinking", None)
    append_thinking_update = patch.pop("append_thinking_update", None)
    for key, value in patch.items():
        if key == "updated_at":
            continue
        progress[key] = value
    if append is not None:
        steps = progress.setdefault("tool_steps", [])
        steps.append(append)
    if append_timeline is not None:
        progress.setdefault("timeline", []).append(append_timeline)
    if append_thinking_update:
        text = str(append_thinking_update).strip()
        if text:
            progress.setdefault("thinking_updates", []).append(text)
    if append_thinking:
        progress["thinking"] = (progress.get("thinking") or "") + append_thinking
        delta = append_thinking.strip()
        if delta:
            tl = progress.setdefault("timeline", [])
            if not tl or tl[-1].get("kind") != "narration" or tl[-1].get("phase") != "plan":
                tl.append({"kind": "narration", "phase": "plan", "text": delta})
            else:
                tl[-1]["text"] = (tl[-1].get("text") or "") + append_thinking
    if append_answer:
        progress["answer"] = (progress.get("answer") or "") + append_answer

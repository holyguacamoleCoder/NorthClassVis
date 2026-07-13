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
    subagent_state: dict[str, Any] = {
        "active": False,
        "kind": "",
        "task_preview": "",
        "inner_steps": [],
        "status": "",
        "turns": 0,
    }

    def _snapshot_subagent() -> dict[str, Any] | None:
        if not subagent_state.get("active"):
            return None
        return {
            "kind": subagent_state.get("kind") or "",
            "task_preview": subagent_state.get("task_preview") or "",
            "inner_steps": list(subagent_state.get("inner_steps") or []),
            "status": subagent_state.get("status") or "running",
            "turns": int(subagent_state.get("turns") or 0),
        }

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
            tool_name = str(event.get("tool") or "")
            if tool_name == "run_subagent":
                params = running.get("params") if isinstance(running.get("params"), dict) else {}
                subagent_state.update({
                    "active": True,
                    "kind": str(params.get("kind") or ""),
                    "task_preview": str(params.get("task") or "")[:240],
                    "inner_steps": [],
                    "status": "running",
                    "turns": 0,
                })
                snap = _snapshot_subagent()
                if snap is not None:
                    patch["running_subagent"] = snap
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
            timeline_item: dict[str, Any] = {"kind": "tool", "phase": "process", "step": step}
            if tool_name == "run_subagent":
                from subagent.result_parse import parse_subagent_tool_result

                parsed = parse_subagent_tool_result(content)
                step["kind"] = "subagent"
                step["subagent"] = {
                    "kind": parsed.get("kind") or subagent_state.get("kind") or params.get("kind"),
                    "task_preview": subagent_state.get("task_preview")
                    or str(params.get("task") or "")[:240],
                    "turns": parsed.get("turns") or subagent_state.get("turns") or 0,
                    "refs": parsed.get("refs") or [],
                    "dataset_ids": parsed.get("dataset_ids") or [],
                    "summary": parsed.get("summary") or "",
                    "error": parsed.get("error"),
                    "inner_steps": list(subagent_state.get("inner_steps") or []),
                    "status": "ok" if parsed.get("ok") else "fail",
                }
                if parsed.get("error") and step.get("status") == "ok":
                    step["status"] = "fail"
                    step["error"] = parsed.get("error")
                timeline_item = {"kind": "subagent", "phase": "process", "step": step}
                subagent_state["active"] = False
                patch["running_subagent"] = None
            patch.update({
                "phase": "tools",
                "hint": "工具执行完成，继续分析…",
                "running_tool": None,
                "append_step": step,
                "append_timeline": timeline_item,
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
        elif et == "subagent_start":
            kind = str(event.get("kind") or "subagent")
            if subagent_state.get("active"):
                subagent_state["kind"] = kind
                subagent_state["status"] = "running"
            snap = _snapshot_subagent()
            patch.update({
                "phase": "subagent",
                "hint": f"子 Agent（{kind}）执行中…",
                "running_tool": None,
            })
            if snap is not None:
                patch["running_subagent"] = snap
        elif et == "subagent_tool_start":
            if subagent_state.get("active"):
                inner = {
                    "call_id": event.get("call_id"),
                    "tool": event.get("tool"),
                    "params": event.get("params") or {},
                    "status": "running",
                    "summary": "执行中…",
                }
                subagent_state.setdefault("inner_steps", []).append(inner)
            snap = _snapshot_subagent()
            if snap is not None:
                patch["running_subagent"] = snap
                patch["phase"] = "subagent"
                tool = str(event.get("tool") or "tool")
                patch["hint"] = f"子 Agent · {tool}…"
        elif et == "subagent_tool_end":
            if subagent_state.get("active"):
                call_id = str(event.get("call_id") or "")
                steps = subagent_state.setdefault("inner_steps", [])
                target = None
                for item in reversed(steps):
                    if call_id and item.get("call_id") == call_id:
                        target = item
                        break
                if target is None and steps:
                    target = steps[-1]
                if target is not None:
                    built = build_tool_step(
                        str(event.get("tool") or target.get("tool") or "tool"),
                        event.get("params")
                        if isinstance(event.get("params"), dict)
                        else target.get("params")
                        or {},
                        str(event.get("content") or ""),
                        call_id=call_id or target.get("call_id"),
                    )
                    target.update({
                        "tool": built.get("tool") or target.get("tool"),
                        "params": built.get("params") or target.get("params") or {},
                        "summary": built.get("summary") or "",
                        "status": built.get("status") or "ok",
                        "resource": built.get("resource"),
                    })
            snap = _snapshot_subagent()
            if snap is not None:
                patch["running_subagent"] = snap
                patch["phase"] = "subagent"
        elif et == "subagent_end":
            kind = str(event.get("kind") or "subagent")
            status = str(event.get("status") or "ok")
            if subagent_state.get("active"):
                subagent_state["kind"] = kind
                subagent_state["status"] = status
                subagent_state["turns"] = int(event.get("turns") or subagent_state.get("turns") or 0)
            snap = _snapshot_subagent()
            patch.update({
                "phase": "subagent",
                "hint": f"子 Agent（{kind}）完成：{status}",
            })
            if snap is not None:
                patch["running_subagent"] = snap
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
        "running_subagent": None,
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

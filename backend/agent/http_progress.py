"""Build incremental job progress events for HTTP polling."""

from __future__ import annotations

import time
from typing import Any, Callable

from .http_adapter import build_tool_step


ProgressCallback = Callable[[dict[str, Any]], None]


def make_job_progress_handler(
    update_fn: Callable[[dict[str, Any]], None],
) -> ProgressCallback:
    """Return a callback AgentLoop / executor can invoke."""

    def handler(event: dict[str, Any]) -> None:
        et = event.get("type")
        patch: dict[str, Any] = {"updated_at": time.time()}

        if et == "llm_start":
            patch.update({"phase": "llm", "hint": "正在调用模型…", "running_tool": None})
        elif et == "tool_start":
            patch.update({
                "phase": "tools",
                "hint": f"正在执行 {event.get('tool', 'tool')}…",
                "running_tool": {
                    "call_id": event.get("call_id"),
                    "tool": event.get("tool"),
                    "params": event.get("params") or {},
                },
            })
        elif et == "tool_end":
            step = build_tool_step(
                str(event.get("tool") or "unknown"),
                event.get("params") if isinstance(event.get("params"), dict) else {},
                str(event.get("content") or ""),
                call_id=str(event.get("call_id") or "") or None,
            )
            patch.update({
                "phase": "tools",
                "hint": "工具执行完成，继续分析…",
                "running_tool": None,
                "append_step": step,
            })
        elif et == "answer":
            patch.update({
                "phase": "answer",
                "hint": "正在整理回答…",
                "answer": str(event.get("content") or ""),
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


def empty_job_progress() -> dict[str, Any]:
    return {
        "phase": "starting",
        "hint": "思考中…",
        "tool_steps": [],
        "running_tool": None,
        "answer": "",
    }


def merge_progress_patch(progress: dict[str, Any], patch: dict[str, Any]) -> None:
    append = patch.pop("append_step", None)
    append_answer = patch.pop("append_answer", None)
    for key, value in patch.items():
        if key == "updated_at":
            continue
        progress[key] = value
    if append is not None:
        steps = progress.setdefault("tool_steps", [])
        steps.append(append)
    if append_answer:
        progress["answer"] = (progress.get("answer") or "") + append_answer

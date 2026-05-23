"""Loop-level hints: data-tool results ↔ session plan (todo_write)."""

from __future__ import annotations

import json
from typing import Any

_DATA_TOOLS = frozenset({"query_data", "aggregate_data"})


def _parse_tool_result_content(content: str) -> dict[str, Any] | None:
    if not content or content.startswith("Error:"):
        return None
    try:
        end = content.find("\n\n[Checks]")
        chunk = content if end < 0 else content[:end]
        return json.loads(chunk)
    except (TypeError, ValueError, json.JSONDecodeError):
        return None


def get_post_data_todo_reminder() -> str | None:
    from tools.handlers.todo_write import plan_is_stale_after_data, todo_manager

    if not todo_manager.state.items:
        return None
    if not plan_is_stale_after_data():
        return None
    return (
        "<reminder>上一步已返回数据结果：请 todo_write 更新进度"
        "（将已完成步骤标 completed，确认是否满足各条 acceptance）。"
        "若 meta.warnings 非空，先修正 query/aggregate 再标完成。</reminder>"
    )


def append_data_tool_checks(
    tool_calls: list[dict[str, Any]],
    tool_results: list[dict[str, Any]],
) -> None:
    """Append plan + warning footers to data tool messages (in place)."""
    by_id = {c.get("id"): c.get("name") for c in tool_calls if c.get("id")}
    had_data = False
    reminder: str | None = None

    for result in tool_results:
        name = by_id.get(result.get("tool_call_id"))
        if name not in _DATA_TOOLS:
            continue
        had_data = True
        content = result.get("content") or ""
        if content.startswith("Error:"):
            continue
        payload = _parse_tool_result_content(content)
        if payload:
            warnings = (payload.get("meta") or {}).get("warnings") or []
            if warnings:
                hint_lines = "\n".join(f"- {w}" for w in warnings)
                block = f"\n\n[Checks]\n{hint_lines}"
                if block not in content:
                    result["content"] = f"{content.strip()}{block}"

    if not had_data:
        return

    has_todo = any(c.get("name") == "todo_write" for c in tool_calls)
    if not has_todo:
        reminder = get_post_data_todo_reminder()

    if not reminder:
        return

    for result in reversed(tool_results):
        name = by_id.get(result.get("tool_call_id"))
        if name in _DATA_TOOLS:
            result["content"] = f"{(result.get('content') or '').strip()}\n\n{reminder}"
            break

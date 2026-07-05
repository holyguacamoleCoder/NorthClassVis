"""Loop-level hints after report write/edit when validation fails."""

from __future__ import annotations

from typing import Any

_WRITE_TOOLS = frozenset({"write_file", "edit_file"})


def report_validation_failed(content: str) -> bool:
    text = content or ""
    if "[Report validate]" not in text:
        return False
    return "status: ERRORS" in text or "\n  error:" in text


def append_report_write_checks(
    tool_calls: list[dict[str, Any]],
    tool_results: list[dict[str, Any]],
) -> None:
    """Append fix reminder when report validation failed (in place)."""
    by_id = {c.get("id"): c.get("name") for c in tool_calls if c.get("id")}
    reminder = (
        "<reminder>报告校验未通过（见上方 [Report validate] 的 error）。"
        "本轮勿向教师宣称报告已完成；请用 edit_file 按 error 逐项修补"
        "（缺章、图表、Evidence 引用标签等），直至 [Report validate: OK] 或仅剩 warn。</reminder>"
    )

    for result in reversed(tool_results):
        name = by_id.get(result.get("tool_call_id"))
        if name not in _WRITE_TOOLS:
            continue
        content = result.get("content") or ""
        if not report_validation_failed(content):
            continue
        if reminder in content:
            return
        result["content"] = f"{content.rstrip()}\n\n{reminder}"
        return

"""Loop-level hints after report write/edit when validation fails."""

from __future__ import annotations

from typing import Any

_WRITE_TOOLS = frozenset({"write_file", "edit_file"})


def report_validation_failed(content: str) -> bool:
    text = content or ""
    if "[Report validate]" not in text:
        return False
    if "Error: Report validation failed" in text:
        return True
    if "status: fail" in text or "status: ERRORS" in text:
        return True
    return False


def append_report_write_checks(
    tool_calls: list[dict[str, Any]],
    tool_results: list[dict[str, Any]],
) -> None:
    """Append fix reminder when report validation failed (in place)."""
    by_id = {c.get("id"): c.get("name") for c in tool_calls if c.get("id")}
    reminder = (
        "<reminder>报告校验存在阻断项（[Report validate] status: fail）。"
        "warn 提醒可暂忽、交付前会自动处理；请只修补 error。"
        "若同一 error 反复出现，先 read_file 再 edit_file。</reminder>"
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

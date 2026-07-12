"""Suggest review_report after all report sections are filled."""

from __future__ import annotations

import re
from typing import Any

_WRITE_TOOLS = frozenset({"write_file", "edit_file"})
_COVERAGE_RE = re.compile(
    r"coverage:\s*(\d+)\s*/\s*(\d+)",
    re.I,
)
_VALIDATE_OK = "[Report validate: OK]"
_REVIEW_MARKER = "[Report review]"


def _tool_result_coverage(content: str) -> tuple[int, int] | None:
    match = _COVERAGE_RE.search(content or "")
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def should_suggest_revision_pass(content: str) -> bool:
    """True when draft write/edit reached full section coverage but not yet OK."""
    text = content or ""
    if _VALIDATE_OK in text:
        return False
    if "[Report validate]" not in text or "status: fail" in text:
        return False
    cov = _tool_result_coverage(text)
    if not cov:
        return False
    present, required = cov
    return required > 0 and present >= required


def append_report_revision_hint(
    tool_calls: list[dict[str, Any]],
    tool_results: list[dict[str, Any]],
) -> None:
    """Append review_report reminder when all sections exist (in place)."""
    by_id = {c.get("id"): c.get("name") for c in tool_calls if c.get("id")}
    reminder = (
        "<reminder>全部必填章节已出现，进入修订阶段：调用 review_report(path=当前报告) "
        "做跨节一致性检查；按返回的 fix 用 edit_file ## <section> 整节替换；"
        "不要整篇 rewrite。修订后再 review_report，直至 status: ok 且 [Report validate: OK]。"
        "</reminder>"
    )

    for result in reversed(tool_results):
        name = by_id.get(result.get("tool_call_id"))
        if name not in _WRITE_TOOLS:
            continue
        content = str(result.get("content") or "")
        if not should_suggest_revision_pass(content):
            continue
        if reminder in content:
            return
        result["content"] = f"{content.rstrip()}\n\n{reminder}"
        return


def turn_used_review_report(turn_messages: list[dict[str, Any]]) -> bool:
    for msg in turn_messages:
        if msg.get("role") != "tool":
            continue
        if _REVIEW_MARKER in str(msg.get("content") or ""):
            return True
    return False

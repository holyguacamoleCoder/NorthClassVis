"""Hints and guards for「继续完成报告」flows."""

from __future__ import annotations

import re
from typing import Any

_CONTINUE_USER_PAT = re.compile(
    r"继续|补全|写完|完成报告|把报告|接着写|还没完成|未完成",
    re.I,
)
_REPORT_PATH_PAT = re.compile(r"reports/[^\s\]]+\.md", re.I)


def messages_since_last_user(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    start = 0
    for idx in range(len(messages) - 1, -1, -1):
        if messages[idx].get("role") == "user":
            start = idx
            break
    return messages[start:]


def latest_report_path(messages: list[dict[str, Any]]) -> str | None:
    paths: list[str] = []
    for msg in messages:
        if msg.get("role") != "tool":
            continue
        content = str(msg.get("content") or "")
        for match in _REPORT_PATH_PAT.finditer(content):
            paths.append(match.group(0).replace("\\", "/"))
    return paths[-1] if paths else None


def turn_has_report_tool_failure(turn_messages: list[dict[str, Any]]) -> bool:
    for msg in turn_messages:
        if msg.get("role") != "tool":
            continue
        content = str(msg.get("content") or "")
        if "reports/" not in content:
            continue
        if content.startswith("Error:") or "Text not found in reports/" in content:
            return True
        if "[Report validate]" in content and "status: ERRORS" in content:
            return True
    return False


def turn_has_report_validate_ok(turn_messages: list[dict[str, Any]]) -> bool:
    for msg in turn_messages:
        if msg.get("role") != "tool":
            continue
        content = str(msg.get("content") or "")
        if "[Report validate: OK]" in content:
            return True
    return False


def should_attach_report_continue_hint(user_message: str | None) -> bool:
    text = (user_message or "").strip()
    return bool(text and _CONTINUE_USER_PAT.search(text))


def format_report_continue_hint(path: str) -> str:
    """Pure hint text for the *current* user turn (do not rewrite history)."""
    return (
        "<reminder>教师要求继续完成报告。"
        f"目标文件：{path}。"
        "必须先 read_file 该路径；edit_file 的 old_text 首行用 ## <章节> 即可整节替换；"
        "若章节尚不存在也会自动追加。"
        "未出现 [Report validate: OK] 前禁止向教师口头宣称报告已完成。</reminder>"
    )


def inject_report_continue_reminder(
    messages: list[dict[str, Any]],
    user_message: str | None,
) -> bool:
    """Deprecated: rewriting history busts prefix cache.

    Prefer ``format_report_continue_hint`` + ``build_turn_agent_hint`` on the
    new user turn only. This no-op remains for old call sites/tests.
    """
    _ = messages, user_message
    return False


def should_replace_report_false_completion(
    turn_messages: list[dict[str, Any]],
    *,
    produce_mode: bool,
) -> bool:
    """Block chat-only「报告已写好」when report tools failed this teacher turn."""
    if not produce_mode:
        return False
    if not turn_has_report_tool_failure(turn_messages):
        return False
    if turn_has_report_validate_ok(turn_messages):
        return False
    return True


def report_false_completion_guard_text(path: str | None = None) -> str:
    target = f"（{path}）" if path else ""
    return (
        "本轮**未能**把修改写入报告文件"
        f"{target}（edit_file 未命中或校验未通过），聊天里的摘要**不能**当作正式报告。\n\n"
        "请让我继续：先 **read_file** 当前报告，再按缺失章节用 `## 章节名` 整节补写；"
        "你也可以 **新建会话**，用真实学号路径重新生成（避免 `学生ID` 占位路径）。"
    )

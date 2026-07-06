"""Structured stop summaries when a user round hits guards or turn limits."""

from __future__ import annotations

import json
import re
from typing import Any

from hints.report_continue import latest_report_path, messages_since_last_user

_REPORT_PATH_RE = re.compile(r"reports/[^\s\]`]+\.md", re.I)
_ERROR_LINE_RE = re.compile(r"^Error:\s*(.+)$", re.MULTILINE)


def _user_question(turn_messages: list[dict[str, Any]]) -> str:
    for msg in turn_messages:
        if msg.get("role") == "user":
            text = str(msg.get("content") or "").strip()
            if text and not text.startswith("/skill"):
                return text[:300]
    return "（未识别）"


def _scan_tool_outcomes(turn_messages: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
    """Returns (completed_one_liners, blocking_errors)."""
    call_names: dict[str, str] = {}
    call_params: dict[str, dict[str, Any]] = {}
    for msg in turn_messages:
        if msg.get("role") != "assistant":
            continue
        for call in msg.get("tool_calls") or []:
            cid = str(call.get("id") or "")
            fn = call.get("function") or {}
            name = str(fn.get("name") or "tool")
            call_names[cid] = name
            raw = fn.get("arguments")
            if isinstance(raw, dict):
                call_params[cid] = raw
            elif isinstance(raw, str):
                try:
                    call_params[cid] = json.loads(raw) if raw else {}
                except json.JSONDecodeError:
                    call_params[cid] = {}

    done: list[str] = []
    errors: list[str] = []
    for msg in turn_messages:
        if msg.get("role") != "tool":
            continue
        cid = str(msg.get("tool_call_id") or "")
        tool = call_names.get(cid, "tool")
        content = str(msg.get("content") or "")
        if content.startswith("Error:") or content.startswith("Permission denied"):
            err = _ERROR_LINE_RE.search(content)
            line = err.group(1).strip() if err else content.split("\n", 1)[0]
            errors.append(f"{tool}: {line[:160]}")
            continue
        if "[Write OK" in content or "[Edit OK" in content:
            path = latest_report_path([msg]) or _REPORT_PATH_RE.search(content)
            if path:
                done.append(f"{tool} → `{path if isinstance(path, str) else path.group(0)}`")
            else:
                done.append(f"{tool} 已写入报告")
            continue
        if tool in ("query_data", "aggregate_data", "inspect_schema"):
            summary = _brief_data_tool_summary(tool, call_params.get(cid, {}), content)
            if summary:
                done.append(summary)
    return done[-8:], errors[-5:]


def _brief_data_tool_summary(tool: str, params: dict[str, Any], content: str) -> str | None:
    resource = params.get("resource") or params.get("class") or params.get("classes")
    if tool == "query_data":
        scanned = None
        m = re.search(r"rows_scanned=(\d+)", content)
        if m:
            scanned = m.group(1)
        elif '"rows_scanned"' in content:
            try:
                payload = json.loads(content[content.find("{") :])
                scanned = str((payload.get("meta") or {}).get("rows_scanned"))
            except (json.JSONDecodeError, TypeError, ValueError):
                pass
        tail = f"，{scanned} 行" if scanned else ""
        return f"query_data {resource or params}{tail}"
    if tool == "aggregate_data":
        if content.startswith("{"):
            try:
                payload = json.loads(content)
                rows = payload.get("rows") or []
                if rows:
                    return f"aggregate_data 完成（{len(rows)} 行结果）"
            except json.JSONDecodeError:
                pass
        return "aggregate_data 完成"
    if tool == "inspect_schema":
        return f"inspect_schema {resource or ''}".strip()
    return None


def build_turn_stop_summary(
    messages: list[dict[str, Any]],
    *,
    reason_title: str,
    turns_used: int | None = None,
    max_turns: int | None = None,
    compact_summary: str | None = None,
    extra_lines: list[str] | None = None,
) -> str:
    turn = messages_since_last_user(messages)
    question = _user_question(turn)
    done, errors = _scan_tool_outcomes(turn)
    report_path = latest_report_path(turn)

    lines = [f"## {reason_title}", ""]
    if turns_used is not None and max_turns is not None:
        lines.append(
            f"**轮次**：已执行 {turns_used} / {max_turns} 轮工具循环，已自动停止以防空转。"
        )
        lines.append("")
    lines.append(f"**本轮问题**：{question}")
    lines.append("")

    if done:
        lines.append("**已完成**")
        for item in done:
            lines.append(f"- {item}")
        lines.append("")

    if errors:
        lines.append("**阻塞 / 未完成**")
        for item in errors:
            lines.append(f"- {item}")
        lines.append("")

    if report_path:
        lines.append(f"**报告草稿**：`{report_path}`")
        lines.append("")

    if compact_summary and compact_summary.strip():
        lines.append("**会话压缩摘要**")
        lines.append(compact_summary.strip()[:600])
        lines.append("")

    if extra_lines:
        for line in extra_lines:
            if line.strip():
                lines.append(line.strip())
        lines.append("")

    lines.append("**建议下一步**：说明要「继续补全」哪一部分，或新建会话简化范围后重试。")
    return "\n".join(lines).strip()

"""Map AgentLoop message history to frontend-friendly HTTP payloads."""

from __future__ import annotations

import json
from typing import Any

_ERROR_PREFIXES = ("Error:", "Permission denied", "Tool blocked")


def _parse_tool_arguments(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return dict(raw)
    if not isinstance(raw, str) or not raw.strip():
        return {}
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        return {}


def _tool_status(content: str) -> str:
    text = (content or "").strip()
    if not text:
        return "fail"
    if text.startswith("Tool blocked"):
        return "blocked"
    if text.startswith("Permission denied"):
        return "denied"
    if any(text.startswith(prefix) for prefix in _ERROR_PREFIXES):
        return "fail"
    return "ok"


def _summarize_tool_content(tool_name: str, content: str, max_len: int = 160) -> str:
    text = (content or "").strip()
    if not text:
        return f"{tool_name} 无返回内容"
    if tool_name == "build_visual_links":
        try:
            payload = json.loads(text)
            links = payload.get("visual_links") or []
            return f"生成 {len(links)} 个图表入口"
        except json.JSONDecodeError:
            pass
    if tool_name in ("query_data", "aggregate_data"):
        try:
            payload = json.loads(text)
            rows = payload.get("rows") or []
            meta = payload.get("meta") or {}
            truncated = meta.get("truncated")
            suffix = "（已截断）" if truncated else ""
            return f"返回 {len(rows)} 行{suffix}"
        except json.JSONDecodeError:
            pass
    one_line = " ".join(text.split())
    if len(one_line) > max_len:
        return one_line[: max_len - 1] + "…"
    return one_line


def _extract_visual_links(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    call_names: dict[str, str] = {}
    for msg in messages:
        if msg.get("role") != "assistant":
            continue
        for call in msg.get("tool_calls") or []:
            fn = call.get("function") or {}
            call_id = call.get("id")
            if call_id:
                call_names[str(call_id)] = str(fn.get("name") or "")

    links: list[dict[str, Any]] = []
    seen: set[str] = set()
    for msg in messages:
        if msg.get("role") != "tool":
            continue
        call_id = str(msg.get("tool_call_id") or "")
        if call_names.get(call_id) != "build_visual_links":
            continue
        try:
            payload = json.loads(msg.get("content") or "{}")
        except json.JSONDecodeError:
            continue
        for link in payload.get("visual_links") or []:
            if not isinstance(link, dict):
                continue
            view = link.get("view")
            params = link.get("params")
            if not view or not isinstance(params, dict):
                continue
            key = json.dumps({"view": view, "params": params}, sort_keys=True, ensure_ascii=False)
            if key in seen:
                continue
            seen.add(key)
            item = {"view": view, "params": params}
            if link.get("label"):
                item["label"] = link["label"]
            links.append(item)
    return links


def build_tool_step(
    tool_name: str,
    params: dict[str, Any],
    content: str,
    *,
    call_id: str | None = None,
) -> dict[str, Any]:
    status = _tool_status(content)
    step: dict[str, Any] = {
        "tool": tool_name,
        "params": dict(params or {}),
        "summary": _summarize_tool_content(tool_name, content),
        "status": status,
    }
    if call_id:
        step["call_id"] = call_id
    if status in ("fail", "denied", "blocked"):
        step["error"] = _summarize_tool_content(tool_name, content, max_len=400)
    return step


def extract_tool_steps(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Build trace.steps[] from assistant tool_calls + tool results."""
    call_map: dict[str, dict[str, Any]] = {}
    for msg in messages:
        if msg.get("role") != "assistant":
            continue
        for call in msg.get("tool_calls") or []:
            fn = call.get("function") or {}
            call_id = call.get("id")
            if not call_id:
                continue
            call_map[str(call_id)] = {
                "tool": str(fn.get("name") or "unknown"),
                "params": _parse_tool_arguments(fn.get("arguments")),
            }

    steps: list[dict[str, Any]] = []
    for msg in messages:
        if msg.get("role") != "tool":
            continue
        call_id = str(msg.get("tool_call_id") or "")
        info = call_map.get(call_id, {"tool": "unknown", "params": {}})
        content = str(msg.get("content") or "")
        status = _tool_status(content)
        step: dict[str, Any] = {
            "tool": info["tool"],
            "params": info["params"],
            "summary": _summarize_tool_content(info["tool"], content),
            "status": status,
        }
        if status in ("fail", "denied", "blocked"):
            step["error"] = _summarize_tool_content(info["tool"], content, max_len=400)
        steps.append(step)
    return steps


def _last_assistant_content(messages: list[dict[str, Any]]) -> str:
    for msg in reversed(messages):
        if msg.get("role") == "assistant" and msg.get("content"):
            return str(msg["content"])
    return ""


def _turn_start_index(messages: list[dict[str, Any]]) -> int:
    for idx in range(len(messages) - 1, -1, -1):
        if messages[idx].get("role") == "user":
            return idx
    return 0


def adapt_legacy_query_response(
    messages: list[dict[str, Any]],
    *,
    continue_reason: str | None = None,
) -> dict[str, Any]:
    """Top-level answer/evidence/trace contract for AgentChatFloat."""
    turn_messages = messages[_turn_start_index(messages) :]
    steps = extract_tool_steps(turn_messages)
    answer = _last_assistant_content(turn_messages)
    evidence = [
        {"tool": step["tool"], "summary": step["summary"]}
        for step in steps
        if step.get("status") == "ok"
    ]
    visual_links = _extract_visual_links(turn_messages)
    actions: list[str] = []
    if visual_links:
        actions.append("点击下方图表入口查看可视化结果")
    if continue_reason in (
        "consult_list_loop_guard",
        "todo_only_loop_guard",
        "tool_loop_guard",
    ):
        actions.append("可切换到「分析」模式后重新提问")

    overall_status = "complete"
    if continue_reason and continue_reason not in ("tool_calls_executed",):
        overall_status = "failed"
    elif any(step.get("status") in ("fail", "denied", "blocked") for step in steps):
        overall_status = "partial" if answer else "failed"

    return {
        "answer": answer,
        "evidence": evidence,
        "actions": actions,
        "visual_links": visual_links,
        "trace": {"steps": steps},
        "continue_reason": continue_reason,
        "goal_check": {
            "is_satisfied": overall_status == "complete" and bool(answer),
            "can_stop_early": overall_status == "complete",
            "reason": continue_reason or "",
            "is_pending_clarification": False,
        },
        "summary": {
            "overall_status": overall_status,
            "key_findings": evidence[:3] and [e["summary"] for e in evidence[:3]] or [],
            "unresolved_points": [
                step.get("error") or step.get("summary") or ""
                for step in steps
                if step.get("status") in ("fail", "denied", "blocked")
            ],
        },
    }


def serialize_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Lightweight message list for frontend rendering."""
    call_names: dict[str, str] = {}
    serialized: list[dict[str, Any]] = []
    for msg in messages:
        role = msg.get("role")
        if role == "user":
            serialized.append({"role": "user", "content": str(msg.get("content") or "")})
            continue
        if role == "assistant":
            item: dict[str, Any] = {
                "role": "assistant",
                "content": msg.get("content"),
            }
            tool_calls = []
            for call in msg.get("tool_calls") or []:
                fn = call.get("function") or {}
                call_id = str(call.get("id") or "")
                name = str(fn.get("name") or "")
                if call_id:
                    call_names[call_id] = name
                tool_calls.append(
                    {
                        "id": call_id,
                        "name": name,
                        "arguments": _parse_tool_arguments(fn.get("arguments")),
                    }
                )
            if tool_calls:
                item["toolCalls"] = tool_calls
            serialized.append(item)
            continue
        if role == "tool":
            call_id = str(msg.get("tool_call_id") or "")
            content = str(msg.get("content") or "")
            serialized.append(
                {
                    "role": "tool",
                    "toolCallId": call_id,
                    "name": call_names.get(call_id, "unknown"),
                    "content": content,
                    "status": _tool_status(content),
                }
            )
    return serialized


def adapt_turn_response(
    session,
    *,
    continue_reason: str | None = None,
    loaded_skills: set[str] | None = None,
) -> dict[str, Any]:
    legacy = adapt_legacy_query_response(
        session.messages,
        continue_reason=continue_reason,
    )
    return {
        **legacy,
        "session_id": session.id,
        "session_title": session.title,
        "permission_mode": session.permission_mode,
        "messages": serialize_messages(session.messages),
        "todo_items": list(session.todo_items or []),
        "filter_context": session.filter_context,
        "loaded_skills": sorted(loaded_skills or []),
    }

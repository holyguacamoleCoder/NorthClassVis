"""Map AgentLoop message history to frontend-friendly HTTP payloads."""

from __future__ import annotations

import json
import re
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


def _skill_name_from_params(params: dict[str, Any]) -> str:
    for key in ("name", "skill_name", "skill"):
        value = params.get(key)
        if value:
            return str(value).strip()
    return ""


def _reference_name_from_params(params: dict[str, Any]) -> str:
    for key in ("name", "reference_name", "reference"):
        value = params.get(key)
        if value:
            return str(value).strip()
    return ""


def _todo_items_from_params(params: dict[str, Any]) -> list[dict[str, str]]:
    raw_items = params.get("items")
    if not isinstance(raw_items, list):
        return []
    items: list[dict[str, str]] = []
    for raw in raw_items:
        if not isinstance(raw, dict):
            continue
        content = str(raw.get("content") or "").strip()
        if not content:
            continue
        row: dict[str, str] = {
            "content": content,
            "status": str(raw.get("status") or "pending").lower(),
        }
        active_form = str(raw.get("active_form") or "").strip()
        if active_form:
            row["active_form"] = active_form
        acceptance = str(raw.get("acceptance") or "").strip()
        if acceptance:
            row["acceptance"] = acceptance
        items.append(row)
    return items


def _todo_snapshot(items: list[dict[str, str]]) -> dict[str, Any]:
    completed = sum(1 for item in items if item.get("status") == "completed")
    return {"items": items, "completed": completed, "total": len(items)}


def _enrich_tool_step(step: dict[str, Any]) -> dict[str, Any]:
    tool_name = str(step.get("tool") or "")
    params = step.get("params") if isinstance(step.get("params"), dict) else {}
    status = step.get("status")

    if tool_name == "todo_write":
        items = _todo_items_from_params(params)
        if items:
            snap = _todo_snapshot(items)
            step["kind"] = "todo"
            step["todo_snapshot"] = snap
            if status == "ok":
                step["summary"] = (
                    f"计划 {snap['completed']}/{snap['total']} 已完成"
                )
    elif tool_name == "load_skill":
        skill_name = _skill_name_from_params(params)
        if skill_name:
            step["kind"] = "skill"
            step["skill_name"] = skill_name
            if status == "ok":
                summary = str(step.get("summary") or "")
                if (
                    "already loaded" in summary.lower()
                    or "已在本会话加载" in summary
                ):
                    step["summary"] = f"技能 {skill_name} 已在本会话加载"
                else:
                    step["summary"] = f"已加载技能 {skill_name}"
    elif tool_name == "load_reference":
        ref_name = _reference_name_from_params(params)
        if ref_name:
            step["kind"] = "reference"
            step["reference_name"] = ref_name
            if status == "ok":
                step["summary"] = f"已加载参考 {ref_name}"
    elif tool_name in ("query_data", "aggregate_data", "inspect_schema"):
        resource = str(params.get("resource") or "").strip()
        if resource:
            step["kind"] = "data"
            step["resource"] = resource
        if status in ("fail", "denied", "blocked") and step.get("error"):
            step["summary"] = _summarize_tool_error(str(step["error"]))
    elif tool_name in ("memory", "save_memory"):
        from ..memory_delivery import memory_event_from_tool

        event = memory_event_from_tool(
            tool_name,
            str(step.get("raw_content") or ""),
            params,
        )
        if event:
            step["kind"] = "memory"
            step["memory_event"] = event
            if status == "ok":
                label = event.get("label") or event.get("name") or event.get("target") or "memory"
                action = event.get("action") or "saved"
                step["summary"] = f"已记住：{label}（{action}）"
    return step


def _summarize_tool_error(text: str, *, max_len: int = 120) -> str:
    body = (text or "").strip()
    if body.startswith("Error:"):
        body = body[6:].strip()
    for sep in ("\n", " | Next:", " | Example:"):
        if sep in body:
            body = body.split(sep, 1)[0].strip()
    body = " ".join(body.split())
    if len(body) > max_len:
        return body[: max_len - 1] + "…"
    return body or "执行失败"


def _summarize_tool_content(tool_name: str, content: str, max_len: int = 160) -> str:
    text = (content or "").strip()
    if not text:
        return f"{tool_name} 无返回内容"
    if tool_name == "todo_write":
        header = re.search(r"\[Plan updated:\s*(\d+)/(\d+)\s+completed\]", text)
        if header:
            return f"计划 {header.group(1)}/{header.group(2)} 已完成"
        if text.startswith("[Plan updated: empty]"):
            return "计划已清空"
    if tool_name == "load_skill":
        fresh = re.search(r'✅ Skill "([^"]+)"', text)
        if fresh:
            return f"已加载技能 {fresh.group(1).strip()}"
        loaded = re.search(r"\[Skill loaded:\s*([^\]]+)\]", text)
        if loaded:
            return f"已加载技能 {loaded.group(1).strip()}"
        active = re.search(r"\[Skill active:\s*([^\]]+)\]", text)
        if active:
            return f"技能 {active.group(1).strip()} 已在本会话加载"
        if "already loaded" in text.lower():
            return "技能已在本会话加载"
    if tool_name == "build_visual_links":
        try:
            payload = json.loads(text)
            links = payload.get("visual_links") or []
            return f"生成 {len(links)} 个图表入口"
        except json.JSONDecodeError:
            pass
    if tool_name in ("memory", "save_memory"):
        from ..memory_delivery import memory_event_from_tool

        event = memory_event_from_tool(tool_name, text, {})
        if event and not text.startswith("Error:"):
            label = event.get("label") or event.get("name") or event.get("target") or "memory"
            return f"已记住：{label}"
    if tool_name in ("query_data", "aggregate_data", "inspect_schema"):
        if text.startswith("Error:"):
            return _summarize_tool_error(text, max_len=max_len)
        try:
            payload = json.loads(text)
            rows = payload.get("rows") or []
            meta = payload.get("meta") or {}
            resource = payload.get("resource") or meta.get("resource") or ""
            truncated = meta.get("truncated")
            suffix = "（已截断）" if truncated else ""
            prefix = f"{resource} · " if resource else ""
            if tool_name == "inspect_schema":
                cols = payload.get("columns") or []
                return f"{prefix}{len(cols)} 列 · {payload.get('row_count_estimate', 0)} 行"
            return f"{prefix}返回 {len(rows)} 行{suffix}"
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


def _extract_report_links(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    from ..report_delivery import report_link_from_tool

    call_names: dict[str, str] = {}
    call_params: dict[str, dict[str, Any]] = {}
    for msg in messages:
        if msg.get("role") != "assistant":
            continue
        for call in msg.get("tool_calls") or []:
            fn = call.get("function") or {}
            call_id = str(call.get("id") or "")
            if call_id:
                call_names[call_id] = str(fn.get("name") or "")
                call_params[call_id] = _parse_tool_arguments(fn.get("arguments"))

    links: list[dict[str, Any]] = []
    seen: set[str] = set()
    for msg in messages:
        if msg.get("role") != "tool":
            continue
        call_id = str(msg.get("tool_call_id") or "")
        tool_name = call_names.get(call_id, str(msg.get("name") or ""))
        if tool_name not in ("write_file", "edit_file"):
            continue
        content = str(msg.get("content") or "")
        if _tool_status(content) != "ok":
            continue
        item = report_link_from_tool(
            tool_name,
            content,
            call_params.get(call_id),
        )
        if not item or item["path"] in seen:
            continue
        seen.add(item["path"])
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
        "raw_content": content,
    }
    if call_id:
        step["call_id"] = call_id
    if status in ("fail", "denied", "blocked"):
        step["error"] = _summarize_tool_content(tool_name, content, max_len=400)
    return _enrich_tool_step(step)


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
        steps.append(
            build_tool_step(
                info["tool"],
                info["params"],
                content,
                call_id=call_id or None,
            )
        )
    return steps


def _last_assistant_content(messages: list[dict[str, Any]]) -> str:
    for msg in reversed(messages):
        if msg.get("role") == "assistant" and msg.get("content"):
            return str(msg["content"])
    return ""


def _turn_thinking_content(messages: list[dict[str, Any]]) -> str:
    """First assistant text in the turn that accompanies tool_calls (pre-tool rationale)."""
    for msg in messages:
        if msg.get("role") != "assistant":
            continue
        text = (msg.get("content") or "").strip()
        if text and msg.get("tool_calls"):
            return text
    return ""


def _first_tool_index(messages: list[dict[str, Any]]) -> int | None:
    for idx, msg in enumerate(messages):
        if msg.get("role") == "tool":
            return idx
    return None


def _split_turn_narrative(
    messages: list[dict[str, Any]],
) -> tuple[str, str, str]:
    """
    Split one user-turn into thinking (pre-tool), answer (first post-tool body),
    and closing (final post-tool assistant without merging into one block).
    """
    first_tool = _first_tool_index(messages)
    thinking = ""
    post_texts: list[str] = []

    for idx, msg in enumerate(messages):
        if msg.get("role") != "assistant":
            continue
        text = str(msg.get("content") or "").strip()
        if not text:
            continue
        if first_tool is not None and idx < first_tool:
            if not thinking:
                thinking = text
        else:
            post_texts.append(text)

    if not post_texts:
        return thinking, "", ""
    if len(post_texts) == 1:
        return thinking, post_texts[0], ""
    return thinking, post_texts[0], post_texts[-1]


def build_turn_timeline(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Chronological interleaved narration + tool steps for one user turn."""
    call_map: dict[str, dict[str, Any]] = {}
    for msg in messages:
        if msg.get("role") != "assistant":
            continue
        for call in msg.get("tool_calls") or []:
            fn = call.get("function") or {}
            call_id = call.get("id")
            if call_id:
                call_map[str(call_id)] = {
                    "tool": str(fn.get("name") or "unknown"),
                    "params": _parse_tool_arguments(fn.get("arguments")),
                }

    first_tool = _first_tool_index(messages)
    timeline: list[dict[str, Any]] = []

    for idx, msg in enumerate(messages):
        role = msg.get("role")
        if role == "assistant":
            text = str(msg.get("content") or "").strip()
            if not text:
                continue
            has_tools = bool(msg.get("tool_calls"))
            if first_tool is not None and idx < first_tool:
                timeline.append({"kind": "narration", "phase": "plan", "text": text})
            elif has_tools:
                timeline.append({"kind": "narration", "phase": "process", "text": text})
            else:
                timeline.append({"kind": "narration", "phase": "conclusion", "text": text})
        elif role == "tool":
            call_id = str(msg.get("tool_call_id") or "")
            info = call_map.get(call_id, {"tool": "unknown", "params": {}})
            content = str(msg.get("content") or "")
            step = build_tool_step(
                info["tool"],
                info["params"],
                content,
                call_id=call_id or None,
            )
            timeline.append({"kind": "tool", "phase": "process", "step": step})

    return timeline


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
    timeline = build_turn_timeline(turn_messages)
    thinking, answer, closing = _split_turn_narrative(turn_messages)
    if not answer and not closing:
        answer = _last_assistant_content(turn_messages)
    elif not thinking:
        thinking = _turn_thinking_content(turn_messages)
    evidence = [
        {"tool": step["tool"], "summary": step["summary"]}
        for step in steps
        if step.get("status") == "ok"
    ]
    visual_links = _extract_visual_links(turn_messages)
    report_links = _extract_report_links(turn_messages)
    actions: list[str] = []
    if visual_links:
        actions.append("点击下方图表入口查看可视化结果")
    if report_links:
        actions.append("使用下方「预览」或「导出」查看生成的报告文件")
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
        "closing": closing,
        "thinking": thinking,
        "evidence": evidence,
        "actions": actions,
        "visual_links": visual_links,
        "report_links": report_links,
        "trace": {"steps": steps},
        "timeline": timeline,
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
    loaded_references: set[str] | None = None,
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
        "loaded_references": sorted(loaded_references or []),
    }

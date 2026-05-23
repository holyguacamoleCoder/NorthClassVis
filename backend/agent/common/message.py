# Athropic规范
# def normalize_message(message):
#     normalized_message = []

#     for msg in message:
#       # 1. 删除内部字段
#       # clean = {"role": msg["role"], "content": msg["content"]}
#       role = msg["role"]
#       content = msg["content"]
#       if isinstance(content, str):
#         clean = {"role": role, "content": content}
#       elif isinstance(content, list):
#         cleaned_content = [
#           {k:v for k,v in block.items() if not k.startswith("_")}
#           for block in content if isinstance(block, dict)
#         ]
#         clean = {"role": role, "content": cleaned_content}
#       else:
#         clean = {"role": role, "content": content}
#       normalized_message.append(clean)
  
#     # 2. 将tool_result补齐
#     # 2.1 先拿到所有的tool_result ID
#     tool_result_ids = set()
#     for msg in normalized_message:
#         if isinstance(msg["content"], list):
#             for block in msg["content"]:
#                 if block.get("type") == "tool_result":
#                     tool_result_ids.add(block.get("tool_use_id"))
    
#     # 2.2 找到没有result的tool，用cancelled补齐（不再运行）
#     # 也就是tool_use_id 不在 tool_result_ids 中的tool
#     for msg in normalized_message:
#       role = msg["role"]
#       content = msg["content"]
#       if role == "assistant" and isinstance(content, list):
#           for block in content:
#               if block.get("type") == "tool_use" and block.get("id") not in tool_result_ids:
#                   normalized_message.append({
#                     "role": "user",
#                     "content": [
#                       {
#                         "type": "tool_result",
#                         "tool_use_id": block.get("id"),
#                         "content": "cancelled"
#                       }
#                     ]
#                   })

#     # 3. 合并连续同角色消息
#     merged_message = [normalized_message[0]] if normalized_message else []
#     for msg in normalized_message[1:]:
#         if msg["role"] == merged_message[-1]["role"]:
#             previous_msg = merged_message[-1]

#             # 如果content是列表，可以直接拼接列表
#             # 如果是字符串，需要构造成列表单元
#             def get_content(content):
#                 if isinstance(content, list):
#                   return content
#                 else:
#                   return [{"type": "text", "text": content}]
              
#             previous_content = get_content(previous_msg["content"])
#             current_content = get_content(msg["content"])
#             previous_msg["content"] = previous_content + current_content
#         else:
#             merged_message.append(msg)
  
#     return merged_message

from __future__ import annotations

import json
from typing import Any


def _arguments_as_json_string(arguments: Any) -> str:
    if arguments is None:
        return "{}"
    if isinstance(arguments, str):
        return arguments
    return json.dumps(arguments, ensure_ascii=False)


def _tool_call_item_to_api_dict(item: Any) -> dict[str, Any] | None:
    if item is None:
        return None
    if isinstance(item, str):
        try:
            item = json.loads(item)
        except (TypeError, ValueError):
            return None
    if not isinstance(item, dict):
        fn = getattr(item, "function", None)
        if fn is None and not hasattr(item, "id"):
            return None
        name = getattr(fn, "name", None) if fn is not None else getattr(item, "name", "")
        raw_args = (
            getattr(fn, "arguments", None)
            if fn is not None
            else getattr(item, "arguments", "{}")
        )
        return {
            "id": str(getattr(item, "id", "") or ""),
            "type": str(getattr(item, "type", "function") or "function"),
            "function": {
                "name": str(name or ""),
                "arguments": _arguments_as_json_string(raw_args),
            },
        }
    fn = item.get("function")
    if isinstance(fn, dict):
        return {
            "id": str(item.get("id") or ""),
            "type": str(item.get("type") or "function"),
            "function": {
                "name": str(fn.get("name") or ""),
                "arguments": _arguments_as_json_string(fn.get("arguments")),
            },
        }
    if item.get("name"):
        return {
            "id": str(item.get("id") or ""),
            "type": "function",
            "function": {
                "name": str(item.get("name") or ""),
                "arguments": _arguments_as_json_string(item.get("arguments")),
            },
        }
    return None


def coerce_tool_calls_for_api(tool_calls: Any) -> list[dict[str, Any]]:
    """Normalize SDK / persisted / legacy shapes to OpenAI Chat Completions tool_calls."""
    if not tool_calls:
        return []
    if isinstance(tool_calls, str):
        try:
            tool_calls = json.loads(tool_calls)
        except (TypeError, ValueError):
            return []
    if not isinstance(tool_calls, list):
        single = _tool_call_item_to_api_dict(tool_calls)
        return [single] if single else []
    out: list[dict[str, Any]] = []
    for item in tool_calls:
        coerced = _tool_call_item_to_api_dict(item)
        if coerced and coerced.get("id"):
            out.append(coerced)
    return out


def _sanitize_tool_protocol(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Drop tool results that are not preceded by assistant tool_calls (OpenAI requirement)."""
    out: list[dict[str, Any]] = []
    i = 0
    while i < len(messages):
        msg = messages[i]
        role = msg.get("role")
        if role == "assistant" and msg.get("tool_calls"):
            expected_ids = {
                str(tc.get("id"))
                for tc in msg["tool_calls"]
                if tc.get("id")
            }
            out.append(msg)
            i += 1
            while i < len(messages) and messages[i].get("role") == "tool":
                tid = str(messages[i].get("tool_call_id") or "")
                if tid and tid in expected_ids:
                    out.append(messages[i])
                    expected_ids.discard(tid)
                i += 1
            continue
        if role == "tool":
            i += 1
            continue
        out.append(msg)
        i += 1
    return out


def repair_stored_message(msg: dict[str, Any]) -> dict[str, Any]:
    """Fix persisted assistant tool_calls before the next LLM request."""
    if msg.get("role") == "assistant" and msg.get("tool_calls"):
        api_calls = coerce_tool_calls_for_api(msg["tool_calls"])
        if api_calls:
            msg = dict(msg)
            msg["tool_calls"] = api_calls
            if not (msg.get("content") or "").strip():
                msg["content"] = None
        else:
            msg = dict(msg)
            msg.pop("tool_calls", None)
    return msg


# Openai规范
def normalize_message(messages):
    """
    Normalize messages for OpenAI Chat Completions tool-calling protocol.
    Keep only required fields and preserve tool linkage.
    """
    normalized_messages = []

    for msg in messages:
        role = msg.get("role")
        content = msg.get("content", "")
        clean = {"role": role}

        if content is None:
            clean["content"] = ""
        elif isinstance(content, str):
            clean["content"] = content
        else:
            clean["content"] = str(content)

        # Preserve OpenAI tool-calling fields (must be list[object], not SDK or str).
        if role == "assistant" and msg.get("tool_calls"):
            api_calls = coerce_tool_calls_for_api(msg["tool_calls"])
            if api_calls:
                clean["tool_calls"] = api_calls
                if not clean.get("content"):
                    clean["content"] = None

        if role == "tool" and msg.get("tool_call_id"):
            clean["tool_call_id"] = msg["tool_call_id"]

        normalized_messages.append(clean)

    # Merge adjacent same-role plain text messages.
    # Never merge across assistant messages containing tool_calls.
    merged_messages = []
    for msg in normalized_messages:
        if not merged_messages:
            merged_messages.append(msg)
            continue

        prev = merged_messages[-1]
        same_role = prev.get("role") == msg.get("role")
        has_tool_calls = ("tool_calls" in prev) or ("tool_calls" in msg)
        has_tool_result_link = ("tool_call_id" in prev) or ("tool_call_id" in msg)
        can_merge = (
            same_role
            and not has_tool_calls
            and not has_tool_result_link
            and prev.get("role") != "tool"
            and isinstance(prev.get("content"), str)
            and isinstance(msg.get("content"), str)
        )

        if can_merge:
            joined = f"{prev['content']}\n{msg['content']}".strip()
            prev["content"] = joined
        else:
            merged_messages.append(msg)

    return _sanitize_tool_protocol(merged_messages)
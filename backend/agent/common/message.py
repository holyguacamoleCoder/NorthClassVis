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

        # Preserve OpenAI tool-calling fields.
        if role == "assistant" and msg.get("tool_calls"):
            clean["tool_calls"] = msg["tool_calls"]

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

    return merged_messages
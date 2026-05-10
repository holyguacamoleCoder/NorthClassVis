import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

from common.llm_client import LLMClient
from common.logger import get_logger, log_event, truncate_for_log
from common.message import normalize_message
from tools import TOOLS, execute_tool_calls
from tools.todo_write import get_todo_reminder, mark_round_without_todo_update

_log = get_logger("loop")

BASE_DIR = Path(__file__).resolve().parents[2]  # NorthClassVision
DATA_DIR = BASE_DIR / "data"

@dataclass
class LoopState:
    messages: List[Dict[str, Any]]
    # loop_config: AgentLoopConfig
    messages_count: int = 1
    turn_count: int = 1
    continue_reason: str | None = None


SYSTEM_PROMPT = f"""
You are a helpful assistant that can help with tasks.
Environment is Windows cmd and your workdir is {DATA_DIR}.
Use todo_write to track multi-step tasks and keep it updated when progress changes.
"""

MAX_TOKENS = 8192


class AgentLoop:
    def __init__(self, loop_state: LoopState, llm_client: LLMClient | None = None):
        self.llm_client = llm_client or LLMClient()
        self.loop_state = loop_state or LoopState(messages=[])

    def run_turn(self):
        

        log_event(
            _log,
            logging.INFO,
            "turn_begin",
            turn=self.loop_state.turn_count,
            messages=len(self.loop_state.messages),
        )
        raw_response = self.llm_client.create_completion(
            system_prompt=SYSTEM_PROMPT,
            messages=normalize_message(self.loop_state.messages),
            tools=TOOLS,
            max_tokens=MAX_TOKENS
        )
        if not raw_response or not getattr(raw_response, "choices", None):
            self.loop_state.continue_reason = "llm_no_response"
            log_event(_log, logging.WARNING, "llm_no_response", turn=self.loop_state.turn_count)
            self.loop_state.messages.append({
                "role": "assistant",
                "content": "LLM 调用失败：未返回有效响应（请检查 API Key、模型配置或网络连接）。",
            })
            return False
        response = raw_response.choices[0]

        # 将LLM的响应添加到messages中（Assistant）
        assistant_message = {
            "role": "assistant",
            "content": response.message.content or "",
        }
        if getattr(response.message, "tool_calls", None):
            assistant_message["tool_calls"] = response.message.tool_calls
        self.loop_state.messages.append(assistant_message)

        # 如果LLM没有工具调用，则结束循环
        if response.finish_reason != "tool_calls":
            self.loop_state.continue_reason = None
            preview = truncate_for_log(response.message.content or "")
            log_event(
                _log,
                logging.INFO,
                "turn_end",
                reason="no_tool_calls",
                finish_reason=response.finish_reason,
                assistant_preview=preview,
            )
            return False

        # 如果LLM有工具调用，则执行工具调用
        tool_calls = self.llm_client.extract_tool_calls(raw_response)
        log_event(
            _log,
            logging.INFO,
            "tool_batch_begin",
            count=len(tool_calls),
            names=[c.get("name") for c in tool_calls],
        )
        tool_results = execute_tool_calls(tool_calls)
        
        # 处理 todo_write 工具调用
        has_todo_write_call = any(c.get("name") == "todo_write" for c in tool_calls)
        if not has_todo_write_call:
            mark_round_without_todo_update()
        else:
            reminder = get_todo_reminder()
            if reminder:
                todo_call_ids = {
                    c.get("id")
                    for c in tool_calls
                    if c.get("name") == "todo_write" and c.get("id")
                }
                for result in tool_results:
                    if result.get("tool_call_id") in todo_call_ids:
                        original = result.get("content") or ""
                        result["content"] = f"{original}\n\n{reminder}".strip()
                        break
        
        if not tool_results:
            # 工具调用失败
            self.loop_state.continue_reason = "tool_calls_failed"
            log_event(_log, logging.WARNING, "tool_batch_empty", turn=self.loop_state.turn_count)
            return False

        # 将工具调用结果添加到messages中（Tool）
        self.loop_state.messages.extend(tool_results)
        self.loop_state.messages_count += (1 + len(tool_results))
        self.loop_state.turn_count += 1
        self.loop_state.continue_reason = "tool_calls_executed"
        log_event(
            _log,
            logging.INFO,
            "turn_end",
            reason="tool_calls_executed",
            tools=len(tool_results),
            next_turn=self.loop_state.turn_count,
        )
        return True

    def run_loop(self):
        log_event(_log, logging.INFO, "loop_begin")
        while self.run_turn():
            pass
        log_event(
            _log,
            logging.INFO,
            "loop_end",
            continue_reason=self.loop_state.continue_reason,
            turn=self.loop_state.turn_count,
            messages=len(self.loop_state.messages),
        )
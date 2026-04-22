import os
import json
import subprocess
from dataclasses import dataclass
from typing import Any, Dict, List
from common.llm_client import LLMClient

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]   # NorthClassVision
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
"""

MAX_TOKENS = 8192

TOOLS = [{
    "type": "function",
    "function": {
        "name": "bash",
        "description": "Run a shell command in the current workspace.",
        "parameters": {
            "type": "object",
            "properties": {"command": {"type": "string"}},
            "required": ["command"],
        },
    },
}]

def run_bash(command: str) -> str:
    dangerous = ["rm -rf /", "sudo", "shutdown", "reboot", "> /dev/"]
    if any(item in command for item in dangerous):
        return "Error: Dangerous command blocked"
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=DATA_DIR,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except subprocess.TimeoutExpired:
        return "Error: Timeout (120s)"
    except (FileNotFoundError, OSError) as e:
        return f"Error: {e}"
    output = (result.stdout + result.stderr).strip()
    return output[:50000] if output else "(no output)"

def execute_tool_calls(response_content) -> list[dict]:
    results = []
    for call in response_content:
        if call.get("name") != "bash":
            continue
        try:
            arguments = call.get("arguments") or "{}"
            parsed_args = json.loads(arguments) if isinstance(arguments, str) else (arguments or {})
        except (TypeError, ValueError):
            parsed_args = {}
        command = parsed_args.get("command")
        if not command:
            continue
        print(f"\033[33m$ {command}\033[0m")
        output = run_bash(command)
        print(output[:200])
        results.append({
            "role": "tool",
            "tool_call_id": call.get("id"),
            "content": output,
        })
    return results

# def execute_tool_calls():
#     print("execute_tool_calls>...")
#     return "tool_calls executed"

class AgentLoop:
    """Stateless loop engine: plan -> execute -> evaluate."""

    def __init__(self, loop_state: LoopState, llm_client: LLMClient | None = None):
        self.llm_client = llm_client or LLMClient()
        self.loop_state = loop_state or LoopState(messages=[])

    def run_turn(self):
        raw_response = self.llm_client.create_completion(
            system_prompt=SYSTEM_PROMPT,
            messages=self.loop_state.messages,
            tools=TOOLS,
            max_tokens=MAX_TOKENS
        )
        if not raw_response or not getattr(raw_response, "choices", None):
            self.loop_state.continue_reason = "llm_no_response"
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
            return False

        # 如果LLM有工具调用，则执行工具调用
        tool_calls = self.llm_client.extract_tool_calls(raw_response)
        tool_resuls = execute_tool_calls(tool_calls)
        if not tool_resuls:
            # 工具调用失败
            self.loop_state.continue_reason = "tool_calls failed"
            return False

        # 将工具调用结果添加到messages中（Tool）
        self.loop_state.messages.extend(tool_resuls)
        self.loop_state.messages_count += (1 + len(tool_resuls))
        self.loop_state.turn_count += 1
        self.loop_state.continue_reason = "tool_calls_executed"
        return True

    def run_loop(self):
        while self.run_turn():
            pass
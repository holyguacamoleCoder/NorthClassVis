# Agent 公共层：契约、上下文、工具函数、日志、LLM、提示词。

from agent.common.contracts import AnswerContract
from agent.common.contracts import PlanStep
from agent.common.contracts import QuestionIntent
from agent.common.contracts import ToolResult
from agent.common.context_utils import normalize_context
from agent.common.log_config import ensure_agent_logger
from agent.common.llm_client import get_default_llm_client
from agent.common.llm_client import LLMClient
from agent.common.prompts import get_compiler_answer_system_prompt
from agent.common.prompts import get_react_agent_system_prompt
from agent.common.prompts import get_react_planner_instruction
from agent.common.prompts import get_react_synthesis_instruction
from agent.common.utils import extract_first_json_object

__all__ = [
    "AnswerContract",
    "PlanStep",
    "QuestionIntent",
    "ToolResult",
    "normalize_context",
    "ensure_agent_logger",
    "get_default_llm_client",
    "LLMClient",
    "get_compiler_answer_system_prompt",
    "get_react_agent_system_prompt",
    "get_react_planner_instruction",
    "get_react_synthesis_instruction",
    "extract_first_json_object",
]

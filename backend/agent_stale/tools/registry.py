# 工具注册表：按名取 Tool 实例，get_openai_tools 由 get_spec 生成；执行请用 tool.call()。
#
# GetContextFilterTool 已移至 context_utils.normalize_context() 调用，待 Step 3 处理；
# 不再注册到 TOOL_REGISTRY。

from typing import Dict, List, Optional

from agent.tools.base import BaseTool
from agent.tools.student_tool import QueryStudentTool
from agent.tools.question_tool import QueryQuestionTool
from agent.tools.knowledge_tool import QueryKnowledgeTool
from agent.tools.class_tool import QueryClassTool


# 4 个厚工具实例，按 name 索引
_ALL_TOOLS: List[BaseTool] = [
    QueryStudentTool(),
    QueryQuestionTool(),
    QueryKnowledgeTool(),
    QueryClassTool(),
]

TOOL_REGISTRY: Dict[str, BaseTool] = {t.name: t for t in _ALL_TOOLS if t.name}


def get_tool(name: str) -> Optional[BaseTool]:
    return TOOL_REGISTRY.get(name)


def get_openai_tools() -> List[Dict]:
    """返回 OpenAI Chat Completions 所需的 tools 列表（全部注册工具）。"""
    return [
        {"type": "function", "function": t.get_spec()}
        for t in TOOL_REGISTRY.values()
    ]


def is_parallel_safe(tool_name: str) -> bool:
    tool = get_tool(tool_name)
    return tool.parallel_safe if tool else True

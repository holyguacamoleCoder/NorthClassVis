# Agent 模块：教师对话编排、工具封装、与前端契约对齐的响应结构。
#
# 对外入口：
#   - Orchestrator.query(question, context) -> response dict
#     当前仅支持 compiler_v1：意图解析 -> 能力规划 -> 执行 -> 答案生成。
#   - ReAct 多轮工具调用入口：agent.react_runner.run_agent(question, context, config, feature_factory)
#     供测试或后续扩展为「compiler / ReAct 双模式」时使用。

from agent.orchestrator import Orchestrator

__all__ = ["Orchestrator"]

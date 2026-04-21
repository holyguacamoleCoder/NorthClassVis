# 规划层校验：任务图合法性（环、工具存在性等）。

from dataclasses import dataclass
from typing import Optional

from agent.common.log_config import ensure_agent_logger
from agent.plan.schemas import TaskGraph
from agent.plan.task_graph import has_cycle

_agent_logger = ensure_agent_logger()


@dataclass
class PlanValidationResult:
    is_valid: bool
    reason: str = ""


def validate_task_graph(graph: TaskGraph) -> PlanValidationResult:
    """校验任务图：无环、节点非空。"""
    if not graph.tasks:
        _agent_logger.debug("Plan validate_task_graph: 空图，视为有效")
        return PlanValidationResult(is_valid=True, reason="空图")
    if has_cycle(graph):
        _agent_logger.warning("Plan validate_task_graph: 存在环，无效")
        return PlanValidationResult(is_valid=False, reason="任务图存在环，无法调度")
    for tid, task in graph.tasks.items():
        if not task.required_tools:
            _agent_logger.warning("Plan validate_task_graph: 任务 %s 未指定工具", tid)
            return PlanValidationResult(is_valid=False, reason=f"任务 {tid} 未指定工具")
    _agent_logger.debug("Plan validate_task_graph: 通过 任务数=%d", len(graph.tasks))
    return PlanValidationResult(is_valid=True)

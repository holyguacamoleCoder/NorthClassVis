# 执行层数据结构：批次、执行计划（依赖 plan 的 TaskGraph 类型）。

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from agent.plan.schemas import TaskGraph


@dataclass
class ExecutionBatch:
    """一批可同时执行的任务（同批内无依赖）。"""
    batch_id: str
    task_ids: List[str]
    parallel: bool = True
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ExecutionPlan:
    """完整执行计划：按批次有序执行。"""
    batches: List[ExecutionBatch] = field(default_factory=list)
    task_graph: Optional[TaskGraph] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "batches": [b.to_dict() for b in self.batches],
            "task_graph": self.task_graph.to_dict() if self.task_graph else None,
        }


@dataclass
class TaskExecutionRecord:
    """单子任务执行记录：用于调度回放、校验与记忆写回。"""

    task_id: str
    tool: str
    params: Dict[str, Any] = field(default_factory=dict)
    status: str = "pending"  # pending | running | ok | fail
    outputs: List[str] = field(default_factory=list)
    verification_rule: str = ""
    result: Optional[Dict[str, Any]] = None
    error: str = ""
    duration_ms: int = 0
    verification_passed: Optional[bool] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

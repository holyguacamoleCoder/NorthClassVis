# 规划层数据结构：子任务、任务图、执行批次。

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class SubTask:
    """单个子任务：输入输出、执行/终止条件、工具、优先级、依赖。"""
    task_id: str
    name: str
    purpose: str = ""

    inputs: Dict[str, Any] = field(default_factory=dict)
    outputs: List[str] = field(default_factory=list)

    required_tools: List[str] = field(default_factory=list)
    tool_params: Dict[str, Any] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)

    execution_condition: str = ""
    termination_condition: str = ""
    verification_rule: str = ""

    priority: int = 100
    parallel_group: Optional[str] = None
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TaskGraph:
    """任务依赖图：节点为 SubTask，边为依赖。"""
    tasks: Dict[str, SubTask] = field(default_factory=dict)
    edges: List[tuple] = field(default_factory=list)  # (from_id, to_id)

    def add_task(self, task: SubTask) -> None:
        self.tasks[task.task_id] = task

    def add_edge(self, from_id: str, to_id: str) -> None:
        self.edges.append((from_id, to_id))

    def task_ids(self) -> List[str]:
        return list(self.tasks.keys())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tasks": {k: v.to_dict() for k, v in self.tasks.items()},
            "edges": list(self.edges),
        }

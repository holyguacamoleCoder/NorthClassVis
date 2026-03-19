# 执行调度：任务图 → 执行批次（可并行层划分）。

from typing import Dict, List

from agent.common.log_config import ensure_agent_logger
from agent.execution.schemas import ExecutionBatch
from agent.execution.schemas import ExecutionPlan
from agent.plan.schemas import TaskGraph
from agent.plan.task_graph import has_cycle
from agent.plan.task_graph import topological_sort

_agent_logger = ensure_agent_logger()


def _get_parallel_batches(graph: TaskGraph) -> List[ExecutionBatch]:
    """
    按依赖划分批次：同一批内任务无依赖，可并行；批与批之间按依赖顺序。
    若图有环，返回单批（按 task_ids 顺序）。
    """
    if has_cycle(graph):
        return [
            ExecutionBatch(
                batch_id="0",
                task_ids=graph.task_ids(),
                parallel=False,
                reason="cycle fallback",
            )
        ]
    order = topological_sort(graph)
    if not order:
        return []
    in_edges: Dict[str, List[str]] = {n: [] for n in graph.task_ids()}
    for a, b in graph.edges:
        if b in in_edges:
            in_edges[b].append(a)
    layer: Dict[str, int] = {}
    for n in order:
        preds = in_edges.get(n) or []
        layer[n] = 1 + max((layer.get(p, 0) for p in preds), default=0)
    by_layer: Dict[int, List[str]] = {}
    for n, L in layer.items():
        by_layer.setdefault(L, []).append(n)
    batches = []
    for L in sorted(by_layer.keys()):
        task_ids = sorted(
            by_layer[L],
            key=lambda tid: graph.tasks[tid].priority if tid in graph.tasks else 0,
            reverse=True,
        )
        batches.append(
            ExecutionBatch(
                batch_id=str(L),
                task_ids=task_ids,
                parallel=len(task_ids) > 1,
                reason=f"layer_{L}",
            )
        )
    return batches


def schedule(graph: TaskGraph) -> ExecutionPlan:
    """将任务图调度为有序批次，同批内可并行。"""
    batches = _get_parallel_batches(graph)
    n_tasks = len(graph.tasks)
    n_batches = len(batches)
    _agent_logger.info(
        "Execution schedule: 任务数=%d 批次数=%s 各批 task_ids=%s",
        n_tasks,
        n_batches,
        [b.task_ids for b in batches],
    )
    return ExecutionPlan(batches=batches, task_graph=graph)

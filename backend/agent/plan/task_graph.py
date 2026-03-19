# 任务图：环检测、拓扑排序（供 plan 校验用；批次划分在 execution/scheduler）。

from typing import Dict, List

from agent.plan.schemas import TaskGraph


def has_cycle(graph: TaskGraph) -> bool:
    """检测是否有环。"""
    ids = set(graph.task_ids())
    if not ids:
        return False
    in_degree: Dict[str, int] = {n: 0 for n in ids}
    out_edges: Dict[str, List[str]] = {n: [] for n in ids}
    for a, b in graph.edges:
        if a in ids and b in ids:
            in_degree[b] += 1
            out_edges[a].append(b)
    queue = [n for n in ids if in_degree[n] == 0]
    count = 0
    while queue:
        n = queue.pop()
        count += 1
        for m in out_edges[n]:
            in_degree[m] -= 1
            if in_degree[m] == 0:
                queue.append(m)
    return count != len(ids)


def topological_sort(graph: TaskGraph) -> List[str]:
    """拓扑排序，返回任务 id 执行顺序（无依赖优先）。"""
    ids = list(graph.task_ids())
    if not ids:
        return []
    in_degree: Dict[str, int] = {n: 0 for n in ids}
    out_edges: Dict[str, List[str]] = {n: [] for n in ids}
    for a, b in graph.edges:
        if a in ids and b in ids:
            in_degree[b] += 1
            out_edges[a].append(b)
    queue = [n for n in ids if in_degree[n] == 0]
    order = []
    while queue:
        n = queue.pop(0)
        order.append(n)
        for m in out_edges[n]:
            in_degree[m] -= 1
            if in_degree[m] == 0:
                queue.append(m)
    return order if len(order) == len(ids) else ids

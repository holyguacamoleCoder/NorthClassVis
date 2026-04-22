"""任务图：环检测、拓扑排序（批次划分在 execution/scheduler）。"""
import pytest

from agent.plan.schemas import SubTask
from agent.plan.schemas import TaskGraph
from agent.plan.task_graph import has_cycle
from agent.plan.task_graph import topological_sort


def test_has_cycle_no_cycle():
    g = TaskGraph()
    g.add_task(SubTask(task_id="a", name="a", required_tools=["t"]))
    g.add_task(SubTask(task_id="b", name="b", required_tools=["t"]))
    g.add_edge("a", "b")
    assert has_cycle(g) is False


def test_has_cycle_with_cycle():
    g = TaskGraph()
    g.add_task(SubTask(task_id="a", name="a", required_tools=["t"]))
    g.add_task(SubTask(task_id="b", name="b", required_tools=["t"]))
    g.add_edge("a", "b")
    g.add_edge("b", "a")
    assert has_cycle(g) is True


def test_topological_sort():
    g = TaskGraph()
    g.add_task(SubTask(task_id="a", name="a", required_tools=["t"]))
    g.add_task(SubTask(task_id="b", name="b", required_tools=["t"]))
    g.add_task(SubTask(task_id="c", name="c", required_tools=["t"]))
    g.add_edge("a", "c")
    g.add_edge("b", "c")
    order = topological_sort(g)
    assert order.index("c") > order.index("a")
    assert order.index("c") > order.index("b")



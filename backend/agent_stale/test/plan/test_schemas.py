"""SubTask、TaskGraph（ExecutionBatch、ExecutionPlan 见 execution 模块）。"""
import pytest

from agent.plan.schemas import SubTask
from agent.plan.schemas import TaskGraph


def test_sub_task_to_dict():
    t = SubTask(task_id="t1", name="query_student", required_tools=["query_student"], tool_params={"mode": "portrait"})
    d = t.to_dict()
    assert d["task_id"] == "t1"
    assert d["required_tools"] == ["query_student"]


def test_task_graph_add_task_and_edges():
    g = TaskGraph()
    g.add_task(SubTask(task_id="t1", name="a", required_tools=["x"]))
    g.add_task(SubTask(task_id="t2", name="b", required_tools=["y"], dependencies=["t1"]))
    g.add_edge("t1", "t2")
    assert len(g.tasks) == 2
    assert ("t1", "t2") in g.edges



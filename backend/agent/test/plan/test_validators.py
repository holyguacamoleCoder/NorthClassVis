"""validate_task_graph。"""
import pytest

from agent.plan.schemas import SubTask
from agent.plan.schemas import TaskGraph
from agent.plan.validators import validate_task_graph


def test_validate_empty_graph():
    g = TaskGraph()
    r = validate_task_graph(g)
    assert r.is_valid is True


def test_validate_acyclic_graph():
    g = TaskGraph()
    g.add_task(SubTask(task_id="a", name="a", required_tools=["t"]))
    g.add_task(SubTask(task_id="b", name="b", required_tools=["t"]))
    g.add_edge("a", "b")
    r = validate_task_graph(g)
    assert r.is_valid is True


def test_validate_cycle():
    g = TaskGraph()
    g.add_task(SubTask(task_id="a", name="a", required_tools=["t"]))
    g.add_task(SubTask(task_id="b", name="b", required_tools=["t"]))
    g.add_edge("a", "b")
    g.add_edge("b", "a")
    r = validate_task_graph(g)
    assert r.is_valid is False
    assert "环" in r.reason

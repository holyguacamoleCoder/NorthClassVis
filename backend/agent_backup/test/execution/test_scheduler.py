"""execution/scheduler.py：schedule、批次划分。"""
import pytest

from agent.execution import schedule
from agent.plan.schemas import SubTask
from agent.plan.schemas import TaskGraph


def test_schedule_returns_plan_with_parallel_batches():
    g = TaskGraph()
    g.add_task(SubTask(task_id="a", name="a", required_tools=["t"]))
    g.add_task(SubTask(task_id="b", name="b", required_tools=["t"]))
    g.add_task(SubTask(task_id="c", name="c", required_tools=["t"]))
    g.add_edge("a", "c")
    g.add_edge("b", "c")
    plan = schedule(g)
    assert plan.task_graph is g
    assert len(plan.batches) >= 2
    first_batch_ids = set(plan.batches[0].task_ids)
    assert "a" in first_batch_ids or "b" in first_batch_ids
    assert "c" not in first_batch_ids or len(first_batch_ids) == 1


def test_schedule_sorts_tasks_by_priority_within_layer():
    g = TaskGraph()
    g.add_task(SubTask(task_id="low", name="low", required_tools=["t"], priority=10))
    g.add_task(SubTask(task_id="high", name="high", required_tools=["t"], priority=90))
    g.add_task(SubTask(task_id="mid", name="mid", required_tools=["t"], priority=50))
    plan = schedule(g)
    assert len(plan.batches) == 1
    assert plan.batches[0].task_ids == ["high", "mid", "low"]

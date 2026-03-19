"""execution/schemas.py：ExecutionBatch、ExecutionPlan。"""
import pytest

from agent.execution.schemas import ExecutionBatch
from agent.execution.schemas import ExecutionPlan
from agent.execution.schemas import TaskExecutionRecord
from agent.plan.schemas import SubTask
from agent.plan.schemas import TaskGraph


def test_execution_batch():
    b = ExecutionBatch(batch_id="0", task_ids=["t1", "t2"], parallel=True)
    assert b.parallel is True
    assert "t1" in b.task_ids


def test_execution_plan_to_dict():
    g = TaskGraph()
    g.add_task(SubTask(task_id="t1", name="n", required_tools=["x"]))
    plan = ExecutionPlan(
        batches=[ExecutionBatch(batch_id="0", task_ids=["t1"], parallel=False)],
        task_graph=g,
    )
    d = plan.to_dict()
    assert len(d["batches"]) == 1
    assert d["batches"][0]["task_ids"] == ["t1"]
    assert d["task_graph"] is not None


def test_task_execution_record_to_dict():
    r = TaskExecutionRecord(
        task_id="t1",
        tool="query_class",
        params={"mode": "trend"},
        status="ok",
        outputs=["class_trend"],
        verification_rule="status==ok",
        result={"summary": "ok"},
        duration_ms=12,
        verification_passed=True,
    )
    d = r.to_dict()
    assert d["task_id"] == "t1"
    assert d["tool"] == "query_class"
    assert d["outputs"] == ["class_trend"]
    assert d["verification_passed"] is True

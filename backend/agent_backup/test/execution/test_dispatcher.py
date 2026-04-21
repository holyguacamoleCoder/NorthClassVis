"""execution/dispatcher.py：按批次串行与批内并行调度。"""

from agent.execution.dispatcher import dispatch, dispatch_batch
from agent.execution.schemas import ExecutionBatch
from agent.execution.schemas import ExecutionPlan
from agent.plan.schemas import SubTask
from agent.plan.schemas import TaskGraph


def test_dispatch_runs_batches_in_order(monkeypatch):
    calls = []

    def _fake_run_plan_steps(plan_steps, config, feature_factory=None):
        _ = config, feature_factory
        one = plan_steps[0]
        calls.append(one["tool"])
        return [
            {
                "tool": one["tool"],
                "input": one["params"],
                "status": "ok",
                "summary": one["reason"] or "",
                "evidence": [],
                "visual_hints": [],
            }
        ]

    monkeypatch.setattr("agent.execution.dispatcher.run_plan_steps", _fake_run_plan_steps)

    graph = TaskGraph()
    graph.add_task(SubTask(task_id="t0", name="q0", required_tools=["query_class"], tool_params={"mode": "trend"}))
    graph.add_task(SubTask(task_id="t1", name="q1", required_tools=["query_student"], tool_params={"mode": "portrait"}))
    graph.add_task(SubTask(task_id="t2", name="q2", required_tools=["query_question"], tool_params={"mode": "dist"}))
    plan = ExecutionPlan(
        task_graph=graph,
        batches=[
            ExecutionBatch(batch_id="0", task_ids=["t0", "t1"], parallel=True),
            ExecutionBatch(batch_id="1", task_ids=["t2"], parallel=False),
        ],
    )

    records = dispatch(plan, config={})
    assert len(records) == 3
    assert [r.task_id for r in records] == ["t0", "t1", "t2"]
    assert [r.tool for r in records] == ["query_class", "query_student", "query_question"]
    assert all(r.status == "ok" for r in records)
    assert calls[0:2] == ["query_class", "query_student"]
    assert calls[2] == "query_question"


def test_dispatch_batch_runs_single_batch(monkeypatch):
    calls = []

    def _fake_run_plan_steps(plan_steps, config, feature_factory=None):
        _ = config, feature_factory
        one = plan_steps[0]
        calls.append(one["tool"])
        return [
            {
                "tool": one["tool"],
                "input": one["params"],
                "status": "ok",
                "summary": one["reason"] or "",
                "evidence": [],
                "visual_hints": [],
            }
        ]

    monkeypatch.setattr("agent.execution.dispatcher.run_plan_steps", _fake_run_plan_steps)

    graph = TaskGraph()
    graph.add_task(SubTask(task_id="t0", name="q0", required_tools=["query_class"], tool_params={"mode": "trend"}))
    batch = ExecutionBatch(batch_id="0", task_ids=["t0"], parallel=False)

    records = dispatch_batch(batch, graph, config={})
    assert len(records) == 1
    assert records[0].task_id == "t0"
    assert records[0].tool == "query_class"
    assert records[0].status == "ok"
    assert calls == ["query_class"]


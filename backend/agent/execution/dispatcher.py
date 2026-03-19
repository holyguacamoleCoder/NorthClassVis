# 执行分发：按 ExecutionPlan 批次执行，记录每个子任务状态。

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List

from agent.common.log_config import ensure_agent_logger
from agent.execution.schemas import ExecutionBatch, ExecutionPlan, TaskExecutionRecord
from agent.tools.runner import run_plan_steps

_agent_logger = ensure_agent_logger()


def _run_task(task, config, feature_factory=None) -> TaskExecutionRecord:
    tool = (task.required_tools[0] if task.required_tools else "") or ""
    params = dict(task.tool_params or {})
    start = time.perf_counter()
    status = "running"
    error = ""
    result = None

    try:
        step = {"tool": tool, "params": params, "reason": task.reason or task.purpose}
        outputs = run_plan_steps([step], config, feature_factory) or []
        result = outputs[0] if outputs else {}
        status = "ok" if (result.get("status") or "ok") == "ok" else "fail"
        error = result.get("error") or ""
    except Exception as ex:
        status = "fail"
        error = str(ex)
        result = {
            "tool": tool,
            "input": params,
            "status": "error",
            "summary": "dispatch exception",
            "error": error,
        }

    duration_ms = int((time.perf_counter() - start) * 1000)
    return TaskExecutionRecord(
        task_id=task.task_id,
        tool=tool,
        params=params,
        status=status,
        outputs=list(getattr(task, "outputs", []) or []),
        verification_rule=(getattr(task, "verification_rule", "") or ""),
        result=result if isinstance(result, dict) else {},
        error=error,
        duration_ms=duration_ms,
    )


def _run_serial(tasks, config, feature_factory=None) -> List[TaskExecutionRecord]:
    return [_run_task(task, config, feature_factory) for task in tasks]


def _run_parallel(tasks, config, feature_factory=None) -> List[TaskExecutionRecord]:
    if not tasks:
        return []
    records = [None] * len(tasks)
    with ThreadPoolExecutor(max_workers=min(len(tasks), 8)) as ex:
        futures = {
            ex.submit(_run_task, task, config, feature_factory): idx for idx, task in enumerate(tasks)
        }
        for fut in as_completed(futures):
            idx = futures[fut]
            try:
                records[idx] = fut.result()
            except Exception as ex:
                task = tasks[idx]
                tool = (task.required_tools[0] if task.required_tools else "") or ""
                records[idx] = TaskExecutionRecord(
                    task_id=task.task_id,
                    tool=tool,
                    params=dict(task.tool_params or {}),
                    status="fail",
                    outputs=list(getattr(task, "outputs", []) or []),
                    verification_rule=(getattr(task, "verification_rule", "") or ""),
                    result={
                        "tool": tool,
                        "input": dict(task.tool_params or {}),
                        "status": "error",
                        "summary": "parallel dispatch exception",
                        "error": str(ex),
                    },
                    error=str(ex),
                    duration_ms=0,
                )
    return [r for r in records if r is not None]


def dispatch_batch(
    batch: ExecutionBatch,
    graph,
    config,
    feature_factory=None,
) -> List[TaskExecutionRecord]:
    """执行单个 ExecutionBatch，返回该批次的 TaskExecutionRecord 列表。"""
    tasks = [graph.tasks[tid] for tid in (batch.task_ids or []) if tid in graph.tasks]
    if not tasks:
        return []
    if batch.parallel and len(tasks) > 1:
        return _run_parallel(tasks, config, feature_factory)
    return _run_serial(tasks, config, feature_factory)


def dispatch(execution_plan: ExecutionPlan, config, feature_factory=None) -> List[TaskExecutionRecord]:
    """按 ExecutionPlan 的 batches 串行调度，返回 TaskExecutionRecord 列表。"""
    if not execution_plan or not execution_plan.task_graph:
        return []
    records: List[TaskExecutionRecord] = []
    graph = execution_plan.task_graph
    for batch in execution_plan.batches or []:
        batch_records = dispatch_batch(batch, graph, config, feature_factory)
        if not batch_records:
            continue
        records.extend(batch_records)
        _agent_logger.debug(
            "Execution dispatch: batch=%s parallel=%s tasks=%d",
            batch.batch_id,
            batch.parallel,
            len(batch_records),
        )
    return records

# 执行编译：将规划模块产出的 TaskGraph/ExecutionPlan 转为执行器可消费的 PlanStep。

from typing import List

from agent.common.contracts import PlanStep
from agent.common.log_config import ensure_agent_logger
from agent.intent.schemas import GoalSpec
from agent.plan.planner import build_task_graph
from agent.execution.scheduler import schedule

_agent_logger = ensure_agent_logger()


def _derive_scope(goal: GoalSpec) -> str:
    """根据 student_ids / title_id / classes / majors 推导 scope（与 intent 层语义一致）。"""
    ids = goal.student_ids or []
    if len(ids) == 1 or (goal.title_id and str(goal.title_id).strip()):
        return "individual"
    if len(ids) > 1 or (goal.classes and len(goal.classes) > 0) or (goal.majors and len(goal.majors) > 0):
        return "selected"
    return "all"


def compile_plan(goal: GoalSpec) -> List[PlanStep]:
    """
    一站式执行编译：GoalSpec → 任务图 → 调度 → PlanStep 列表。
    规划与执行编译职责解耦后，此函数归 execution 模块。
    """
    _agent_logger.info(
        "Execution compile_plan: 开始 subject=%s mode=%s needs_clarification=%s",
        goal.subject,
        goal.mode,
        goal.needs_clarification,
    )
    if goal.needs_clarification:
        _agent_logger.info("Execution compile_plan: 跳过，needs_clarification=True")
        return []
    goal.scope = _derive_scope(goal)
    _agent_logger.debug("Execution compile_plan: scope=%s", goal.scope)
    graph = build_task_graph(goal)
    if not graph.tasks:
        _agent_logger.info("Execution compile_plan: 任务图为空，返回 0 步")
        return []
    execution_plan = schedule(graph)
    steps = compile_execution_plan_to_steps(execution_plan)
    _agent_logger.info("Execution compile_plan: 完成 steps=%d tools=%s", len(steps), [s.tool for s in steps])
    return steps


def compile_execution_plan_to_steps(plan) -> List[PlanStep]:
    """将 ExecutionPlan 展平为按批次顺序的 PlanStep 列表。"""
    steps = []
    for batch in plan.batches:
        for task_id in batch.task_ids:
            task = plan.task_graph.tasks.get(task_id)
            if not task or not task.required_tools:
                continue
            tool_name = task.required_tools[0]
            params = task.tool_params or {}
            steps.append(
                PlanStep(
                    tool=tool_name,
                    params=params,
                    reason=task.reason or task.purpose,
                    outputs=getattr(task, "outputs", []) or [],
                    verification_rule=getattr(task, "verification_rule", "") or "",
                )
            )
    return steps

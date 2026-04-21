from agent.execution.schemas import TaskExecutionRecord
from agent.intent.schemas import GoalSpec
from agent.output.goal_checker import check_goal_completion
from agent.common.contracts import ToolResult


def test_goal_checker_single_stage_satisfied():
    goal = GoalSpec(subject=["class"], mode=["trend"])
    rec = TaskExecutionRecord(task_id="t1", tool="query_class", params={"mode": "trend"}, status="ok")
    tr = ToolResult(tool="query_class", params={"mode": "trend"}, status="ok", coverage={"covered": True})

    res = check_goal_completion(goal, [rec], [tr])
    assert res.is_satisfied is True
    assert res.can_stop_early is True
    assert not res.missing_requirements


def test_goal_checker_multi_stage_not_yet_satisfied():
    goal = GoalSpec(
        sub_goals=[
            {"subject": ["class"], "mode": ["trend"]},
            {"subject": ["student"], "mode": ["portrait"]},
        ]
    )
    rec = TaskExecutionRecord(task_id="t1", tool="query_class", params={"mode": "trend"}, status="ok")
    tr = ToolResult(tool="query_class", params={"mode": "trend"}, status="ok", coverage={"covered": True})

    res = check_goal_completion(goal, [rec], [tr])
    assert res.is_satisfied is False
    assert res.can_stop_early is False
    assert any("student" in m for m in res.missing_requirements)


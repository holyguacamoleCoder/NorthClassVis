from agent.loop import AgentLoop
from agent.loop import AgentLoopConfig
from agent.loop import ExecutionObservation
from agent.loop import PlannedAction
from agent.loop import STATE_DONE


def test_loop_reaches_done_when_draft_ready():
    loop = AgentLoop(AgentLoopConfig(max_rounds=3))

    def planner(round_idx, question, context, observations):
        if round_idx == 0:
            return PlannedAction(name="parse")
        if round_idx == 1:
            return PlannedAction(name="synthesize")
        return None

    def executor(action, context):
        if action.name == "synthesize":
            return ExecutionObservation(status="ok", summary="done", payload={"draft_ready": True})
        return ExecutionObservation(status="ok", summary="progress", payload={})

    def evaluator(question, observations):
        if observations[-1].payload.get("draft_ready"):
            return STATE_DONE
        return "REPLAN"

    result = loop.run("班级情况", {}, planner, executor, evaluator)
    assert result.final_state == STATE_DONE
    assert result.stop_reason == "terminal_done"
    assert len(result.traces) == 2


def test_loop_enters_clarify_when_planner_returns_none():
    loop = AgentLoop(AgentLoopConfig(max_rounds=2))

    def planner(round_idx, question, context, observations):
        return None

    def executor(action, context):
        return ExecutionObservation(status="ok", summary="n/a")

    def evaluator(question, observations):
        return "REPLAN"

    result = loop.run("?", {}, planner, executor, evaluator)
    assert result.final_state == "CLARIFY"
    assert result.stop_reason == "planner_no_action"
    assert len(result.traces) == 1

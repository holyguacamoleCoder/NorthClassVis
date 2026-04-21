from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


STATE_INIT = "INIT"
STATE_REPLAN = "REPLAN"
STATE_DONE = "DONE"
STATE_FAILED = "FAILED"
STATE_CLARIFY = "CLARIFY"

TERMINAL_STATES = {STATE_DONE, STATE_FAILED, STATE_CLARIFY}


@dataclass
class AgentLoopConfig:
    max_rounds: int = 3


@dataclass
class PlannedAction:
    name: str
    params: Dict[str, Any] = field(default_factory=dict)
    reason: str = ""


@dataclass
class ExecutionObservation:
    status: str
    summary: str
    payload: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RoundTrace:
    round: int
    state: str
    reason: str
    action: Optional[Dict[str, Any]]
    observation: Optional[Dict[str, Any]]


@dataclass
class LoopResult:
    final_state: str
    stop_reason: str
    observations: List[ExecutionObservation]
    traces: List[RoundTrace]


Planner = Callable[[int, str, Dict[str, Any], List[ExecutionObservation]], Optional[PlannedAction]]
Executor = Callable[[PlannedAction, Dict[str, Any]], ExecutionObservation]
Evaluator = Callable[[str, List[ExecutionObservation]], str]


class AgentLoop:
    """Stateless loop engine: plan -> execute -> evaluate."""

    def __init__(self, config: Optional[AgentLoopConfig] = None):
        self.config = config or AgentLoopConfig()

    def run(
        self,
        question: str,
        context: Optional[Dict[str, Any]],
        planner: Planner,
        executor: Executor,
        evaluator: Evaluator,
    ) -> LoopResult:
        normalized_context = dict(context or {})
        observations: List[ExecutionObservation] = []
        traces: List[RoundTrace] = []
        state = STATE_INIT
        stop_reason = "max_rounds_reached"

        for round_idx in range(self.config.max_rounds):
            action = planner(round_idx, question, normalized_context, observations)
            if action is None:
                state = STATE_CLARIFY
                stop_reason = "planner_no_action"
                traces.append(
                    RoundTrace(
                        round=round_idx,
                        state=state,
                        reason="当前信息不足，未生成可执行动作。",
                        action=None,
                        observation=None,
                    )
                )
                break

            observation = executor(action, normalized_context)
            observations.append(observation)
            state = evaluator(question, observations)

            traces.append(
                RoundTrace(
                    round=round_idx,
                    state=state,
                    reason=action.reason or "",
                    action={"name": action.name, "params": dict(action.params or {})},
                    observation={
                        "status": observation.status,
                        "summary": observation.summary,
                        "payload": dict(observation.payload or {}),
                    },
                )
            )

            if state in TERMINAL_STATES:
                stop_reason = f"terminal_{state.lower()}"
                break

        return LoopResult(
            final_state=state,
            stop_reason=stop_reason,
            observations=observations,
            traces=traces,
        )

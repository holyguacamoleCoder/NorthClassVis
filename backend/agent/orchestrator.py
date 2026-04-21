from typing import Any, Dict, List, Optional

from .loop import AgentLoop
from .loop import AgentLoopConfig
from .loop import ExecutionObservation
from .loop import STATE_CLARIFY
from .policy import build_answer
from .policy import check_clarification
from .policy import evaluate_progress
from .policy import execute_action
from .policy import normalize_question
from .policy import plan_round


class Orchestrator:
    """Thin composition layer for API-facing query workflow."""

    def __init__(self, config: Any, feature_factory: Any = None):
        self.config = config
        self.feature_factory = feature_factory
        self.loop = AgentLoop(AgentLoopConfig(max_rounds=3))

    def query(self, question: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        normalized_question = normalize_question(question)
        if not normalized_question:
            return self._empty_response("请输入问题。")

        ctx = dict(context or {})
        clarify = check_clarification(normalized_question, ctx)
        if clarify:
            return self._response(
                answer=build_answer(STATE_CLARIFY, [], clarify.message),
                evidence=[],
                actions=self._clarify_actions(clarify.required_fields),
                trace={
                    "mode": "agent_loop_v1",
                    "state": STATE_CLARIFY,
                    "stop_reason": "precheck_clarification",
                    "steps": [],
                    "required_fields": clarify.required_fields,
                },
            )

        run_result = self.loop.run(
            question=normalized_question,
            context=ctx,
            planner=plan_round,
            executor=execute_action,
            evaluator=evaluate_progress,
        )
        observations: List[ExecutionObservation] = run_result.observations
        answer = build_answer(run_result.final_state, observations)

        return self._response(
            answer=answer,
            evidence=[obs.summary for obs in observations if obs.summary],
            actions=self._post_actions(run_result.final_state),
            trace={
                "mode": "agent_loop_v1",
                "state": run_result.final_state,
                "stop_reason": run_result.stop_reason,
                "steps": [
                    {
                        "round": t.round,
                        "state": t.state,
                        "reason": t.reason,
                        "action": t.action,
                        "observation": t.observation,
                    }
                    for t in run_result.traces
                ],
            },
        )

    def _post_actions(self, final_state: str) -> List[str]:
        if final_state == "DONE":
            return [
                "接入真实查询工具（class/student/question）",
                "将规则回答替换为模板+LLM",
            ]
        if final_state == "FAILED":
            return ["重试问题", "检查上下文参数"]
        return ["补充问题信息"]

    def _clarify_actions(self, required_fields: List[str]) -> List[str]:
        out = []
        if "scope" in required_fields:
            out.append("补充分析范围（班级/学生/知识点/题目）")
        if "question" in required_fields:
            out.append("补充完整问题描述")
        return out or ["补充更多信息"]

    def _response(self, answer: str, evidence: List[str], actions: List[str], trace: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "answer": answer,
            "evidence": evidence,
            "actions": actions,
            "visual_links": [],
            "trace": trace,
        }

    def _empty_response(self, message: str) -> Dict[str, Any]:
        return self._response(message, [], [], {"steps": []})


class Orchestrator:
    def __init__(self, config: Any):
        
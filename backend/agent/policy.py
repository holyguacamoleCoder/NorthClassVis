from dataclasses import dataclass
from typing import Dict, List, Optional

from .loop import ExecutionObservation
from .loop import PlannedAction
from .loop import STATE_CLARIFY
from .loop import STATE_DONE
from .loop import STATE_FAILED
from .loop import STATE_REPLAN


@dataclass
class ClarificationNeed:
    required_fields: List[str]
    message: str


def normalize_question(question: str) -> str:
    return (question or "").strip()


def check_clarification(question: str, context: Optional[Dict]) -> Optional[ClarificationNeed]:
    q = normalize_question(question)
    if len(q) < 3:
        return ClarificationNeed(
            required_fields=["question"],
            message="问题过短，请补充具体分析对象。",
        )
    if not any(token in q for token in ("班", "学生", "知识点", "题", "趋势", "画像")):
        return ClarificationNeed(
            required_fields=["scope"],
            message="请说明分析范围，例如班级、学生、知识点或题目。",
        )
    return None


def plan_round(
    round_idx: int,
    question: str,
    _context: Dict,
    observations: List[ExecutionObservation],
) -> Optional[PlannedAction]:
    if round_idx == 0:
        return PlannedAction(
            name="parse_intent",
            params={"question": question},
            reason="先解析意图，确定分析范围。",
        )
    if round_idx == 1 and observations:
        return PlannedAction(
            name="synthesize_answer",
            params={"observation_count": len(observations)},
            reason="基于已有观察生成回答。",
        )
    return None


def execute_action(action: PlannedAction, _context: Dict) -> ExecutionObservation:
    if action.name == "parse_intent":
        q = str(action.params.get("question") or "")
        return ExecutionObservation(
            status="ok",
            summary="已解析问题意图。",
            payload={"parsed_scope": "generic", "question_length": len(q)},
        )
    if action.name == "synthesize_answer":
        return ExecutionObservation(
            status="ok",
            summary="已生成基础回答草案。",
            payload={"draft_ready": True},
        )
    return ExecutionObservation(
        status="error",
        summary=f"未知动作: {action.name}",
        payload={"action": action.name},
    )


def evaluate_progress(_question: str, observations: List[ExecutionObservation]) -> str:
    if not observations:
        return STATE_FAILED
    latest = observations[-1]
    if latest.status == "error":
        return STATE_FAILED
    if latest.payload.get("draft_ready"):
        return STATE_DONE
    return STATE_REPLAN


def build_answer(final_state: str, observations: List[ExecutionObservation], clarify_message: str = "") -> str:
    if final_state == STATE_CLARIFY:
        return clarify_message or "需要更多信息，请补充分析对象。"
    if final_state == STATE_FAILED:
        return "分析失败，请稍后重试。"
    if final_state == STATE_DONE:
        return "已完成基础 Agent Loop。下一步可接入真实数据工具以输出具体结论。"
    if observations:
        return observations[-1].summary
    return "分析进行中。"

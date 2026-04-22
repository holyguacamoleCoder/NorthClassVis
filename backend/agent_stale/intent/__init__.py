# 意图/目标解析：解析 → 校验 → 追问。规划（compile_plan）已迁至 plan 模块。

from agent.intent.schemas import GoalSpec
from agent.intent.goal_parser import parse_goal
from agent.intent.validator import ValidationResult
from agent.intent.validator import validate
from agent.intent.clarifier import apply_clarification
from agent.intent.clarifier import build_clarification_question
from agent.intent.clarifier import needs_clarification
from agent.intent.followup import merge_followup_goal

parse_intent = parse_goal

__all__ = [
    "GoalSpec",
    "parse_goal",
    "parse_intent",
    "ValidationResult",
    "validate",
    "apply_clarification",
    "needs_clarification",
    "build_clarification_question",
    "merge_followup_goal",
]

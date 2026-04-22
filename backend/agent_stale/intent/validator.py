# 目标合法性校验：能力范围（枚举）+ 安全规范（非学情）。
# 不依赖 plan：仅校验 subject/mode 在合法枚举内，具体能否被规划由 plan 模块负责。

from dataclasses import dataclass

from agent.intent.schemas import GoalSpec

VALID_SUBJECTS = {"student", "question", "knowledge", "class"}
VALID_MODES = {"trend", "portrait", "cluster", "detail"}


@dataclass
class ValidationResult:
    is_valid: bool
    reason: str = ""


def validate(goal: GoalSpec) -> ValidationResult:
    """
    校验目标是否在 Agent 能力范围内、是否符合安全规范。
    - 非学情（is_out_of_domain）→ 不执行
    - subject / mode 非空且均在合法枚举内 → 能力范围内（具体能否产出步骤由 plan 决定）
    """
    if goal.is_out_of_domain:
        return ValidationResult(is_valid=False, reason="非学情问题，不在能力范围内")

    subjects = goal.subject or []
    modes = goal.mode or []
    if not subjects or not modes:
        return ValidationResult(is_valid=False, reason="subject 或 mode 为空")
    if not all(s in VALID_SUBJECTS for s in subjects):
        return ValidationResult(is_valid=False, reason=f"subject 含非法值，合法为 {VALID_SUBJECTS}")
    if not all(m in VALID_MODES for m in modes):
        return ValidationResult(is_valid=False, reason=f"mode 含非法值，合法为 {VALID_MODES}")
    return ValidationResult(is_valid=True)

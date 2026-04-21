# 目标解析模块：结构化目标表示，供解析、校验、追问、编译使用。

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


def _default_sub_goals() -> List[Dict[str, Any]]:
    return []


@dataclass
class GoalSpec:
    """
    用户目标的结构化表示。
    核心需求（subject/mode/scope）、有序子目标（sub_goals）、约束条件、状态分离。
    """

    # ── 核心需求（与 sub_goals 一致：有 sub_goals 时为其并集/顺序的扁平化）
    subject: List[str] = field(default_factory=lambda: ["class"])
    mode: List[str] = field(default_factory=lambda: ["portrait"])
    scope: str = "all"

    # ── 有序子目标（复合意图时 LLM 输出多阶段，plan 可据此做多步与依赖）
    # 每项: {"subject": ["class"], "mode": ["trend"], "title_id": null, "knowledge": null, "time_window": ""}
    sub_goals: List[Dict[str, Any]] = field(default_factory=_default_sub_goals)

    def __post_init__(self) -> None:
        """未提供 sub_goals 时，按 subject/mode 生成单阶段，保证一致性。"""
        if not self.sub_goals and self.subject and self.mode:
            self.sub_goals = [{"subject": list(self.subject), "mode": list(self.mode)}]

    # ── 输出要求（可选，后续 NLG 可据此调整）
    output_depth: str = "summary"  # summary | detailed
    output_format: str = "text"  # text | chart | table

    # ── 约束条件
    student_ids: List[str] = field(default_factory=list)
    knowledge: Optional[str] = None
    title_id: Optional[str] = None
    classes: List[str] = field(default_factory=list)
    majors: List[str] = field(default_factory=list)
    time_window: str = ""

    # ── 兼容与扩展
    intent_type: str = "overview"
    metric: str = ""

    # ── 状态
    is_out_of_domain: bool = False
    needs_clarification: bool = False
    clarification_question: str = ""
    confidence: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

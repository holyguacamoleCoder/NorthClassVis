from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class QuestionIntent:
    intent_type: str
    subject: List[str] = field(default_factory=lambda: ["class"])
    mode: List[str] = field(default_factory=lambda: ["portrait"])
    scope: str = "all"
    is_out_of_domain: bool = False
    metric: str = ""
    knowledge: Optional[str] = None
    title_id: Optional[str] = None
    student_ids: List[str] = field(default_factory=list)
    classes: List[str] = field(default_factory=list)
    majors: List[str] = field(default_factory=list)
    time_window: str = ""
    needs_clarification: bool = False
    clarification_question: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PlanStep:
    tool: str
    params: Dict[str, Any] = field(default_factory=dict)
    reason: str = ""
    outputs: List[str] = field(default_factory=list)
    verification_rule: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ToolResult:
    tool: str
    params: Dict[str, Any] = field(default_factory=dict)
    status: str = "ok"
    summary: str = ""
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    visual_hints: List[Dict[str, Any]] = field(default_factory=list)
    raw: Optional[Dict[str, Any]] = None
    duration_ms: int = 0
    coverage: Dict[str, Any] = field(default_factory=dict)
    quality: Dict[str, Any] = field(default_factory=dict)
    error: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AnswerContract:
    answer: str
    actions: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

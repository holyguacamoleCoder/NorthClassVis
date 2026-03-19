from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class GoalCheckResult:
    is_satisfied: bool
    can_stop_early: bool
    reason: str = ""
    missing_requirements: List[str] = field(default_factory=list)
    supporting_task_ids: List[str] = field(default_factory=list)
    confidence: float = 0.0


@dataclass
class ResultSummary:
    overall_status: str
    completed_task_ids: List[str] = field(default_factory=list)
    failed_task_ids: List[str] = field(default_factory=list)
    partial_task_ids: List[str] = field(default_factory=list)
    key_findings: List[str] = field(default_factory=list)
    unresolved_points: List[str] = field(default_factory=list)
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    visual_links: List[Dict[str, Any]] = field(default_factory=list)


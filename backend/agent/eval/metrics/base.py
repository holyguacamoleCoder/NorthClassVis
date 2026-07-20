"""Metric plugin protocol and helpers."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Protocol

from eval.schema import Scenario
from eval.trace import RunTrace


@dataclass
class MetricResult:
    name: str
    passed: bool
    score: float | None = None  # 0..1 when applicable
    detail: str = ""
    tags: list[str] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)
    hard_gate: bool = True  # False for efficiency metrics

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class Metric(Protocol):
    name: str

    def applicable(self, scenario: Scenario) -> bool: ...

    def evaluate(self, scenario: Scenario, trace: RunTrace) -> list[MetricResult]: ...


def dig_path(data: Any, path: str) -> Any:
    """Resolve dotted / bracket-ish path: a.b.0.c"""
    cur = data
    for part in path.replace("[", ".").replace("]", "").split("."):
        if not part:
            continue
        if cur is None:
            return None
        if isinstance(cur, dict):
            cur = cur.get(part)
            continue
        if isinstance(cur, (list, tuple)):
            try:
                cur = cur[int(part)]
            except (ValueError, IndexError):
                return None
            continue
        return None
    return cur


def compare_value(
    actual: Any,
    *,
    eq: Any = None,
    gte: Any = None,
    lte: Any = None,
    contains: Any = None,
    exists: bool | None = None,
) -> tuple[bool, str]:
    if exists is True and actual is None:
        return False, "expected path to exist"
    if exists is False and actual is not None:
        return False, f"expected path missing, got {actual!r}"
    if eq is not None and actual != eq:
        return False, f"expected eq={eq!r} got {actual!r}"
    if gte is not None:
        try:
            if actual is None or float(actual) < float(gte):
                return False, f"expected gte={gte!r} got {actual!r}"
        except (TypeError, ValueError):
            return False, f"cannot compare gte={gte!r} vs {actual!r}"
    if lte is not None:
        try:
            if actual is None or float(actual) > float(lte):
                return False, f"expected lte={lte!r} got {actual!r}"
        except (TypeError, ValueError):
            return False, f"cannot compare lte={lte!r} vs {actual!r}"
    if contains is not None:
        if isinstance(actual, str):
            if str(contains) not in actual:
                return False, f"expected contains={contains!r} in {actual!r}"
        elif isinstance(actual, (list, tuple, set)):
            if contains not in actual:
                return False, f"expected contains={contains!r} in {actual!r}"
        else:
            return False, f"cannot check contains on {type(actual).__name__}"
    return True, "ok"

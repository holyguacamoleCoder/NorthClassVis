"""目标合法性校验：能力范围、非学情。"""
import pytest

from agent.intent.schemas import GoalSpec
from agent.intent.validator import ValidationResult
from agent.intent.validator import validate


def test_validate_out_of_domain():
    goal = GoalSpec(is_out_of_domain=True, subject=["class"], mode=["trend"])
    r = validate(goal)
    assert r.is_valid is False
    assert "非学情" in r.reason or "能力" in r.reason


def test_validate_supported_combination():
    goal = GoalSpec(subject=["class"], mode=["trend"], is_out_of_domain=False)
    r = validate(goal)
    assert r.is_valid is True


def test_validate_student_portrait():
    goal = GoalSpec(subject=["student"], mode=["portrait"])
    r = validate(goal)
    assert r.is_valid is True


def test_validate_invalid_subject_enum():
    goal = GoalSpec(subject=["unknown_subject"], mode=["portrait"])
    r = validate(goal)
    assert r.is_valid is False
    assert "subject" in r.reason.lower() or "非法" in r.reason

"""追问模块：needs_clarification、build_clarification_question、apply_clarification。"""
import pytest

from agent.intent.schemas import GoalSpec
from agent.intent.clarifier import needs_clarification
from agent.intent.clarifier import build_clarification_question
from agent.intent.clarifier import apply_clarification


def test_needs_clarification_student_no_ids():
    goal = GoalSpec(subject=["student"], student_ids=[])
    assert needs_clarification(goal) is True
    assert "学生" in build_clarification_question(goal)


def test_needs_clarification_knowledge_no_slot():
    goal = GoalSpec(subject=["knowledge"], knowledge=None)
    assert needs_clarification(goal) is True
    assert "知识点" in build_clarification_question(goal)


def test_no_clarification_for_scope_selected_without_student_subject():
    """scope=selected 且无 student_ids 时，若 subject 非 student 则不追问（班级/知识点等不强制要学生）。"""
    goal = GoalSpec(scope="selected", subject=["class"], mode=["trend"], student_ids=[])
    assert needs_clarification(goal) is False
    assert build_clarification_question(goal) == ""


def test_no_clarification_when_complete():
    goal = GoalSpec(subject=["class"], mode=["trend"], student_ids=[], scope="all")
    assert needs_clarification(goal) is False
    assert build_clarification_question(goal) == ""


def test_apply_clarification_sets_question():
    goal = GoalSpec(subject=["knowledge"], knowledge=None)
    apply_clarification(goal)
    assert goal.needs_clarification is True
    assert goal.clarification_question
    assert "知识点" in goal.clarification_question

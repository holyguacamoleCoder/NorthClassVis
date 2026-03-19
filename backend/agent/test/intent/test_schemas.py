"""GoalSpec 数据结构与 to_dict 行为。"""
import pytest

from agent.intent.schemas import GoalSpec


def test_goal_spec_defaults():
    g = GoalSpec()
    assert g.subject == ["class"]
    assert g.mode == ["portrait"]
    assert g.scope == "all"
    assert g.is_out_of_domain is False
    assert g.needs_clarification is False
    assert g.student_ids == []
    assert g.output_depth == "summary"
    assert g.confidence == 1.0


def test_goal_spec_to_dict():
    g = GoalSpec(subject=["student"], mode=["trend"], student_ids=["s1"])
    d = g.to_dict()
    assert d["subject"] == ["student"]
    assert d["mode"] == ["trend"]
    assert d["student_ids"] == ["s1"]
    assert "intent_type" in d
    assert "is_out_of_domain" in d

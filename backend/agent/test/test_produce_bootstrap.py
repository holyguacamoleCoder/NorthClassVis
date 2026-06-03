"""Produce-mode report reference bootstrap."""

import runtime_bootstrap  # noqa: F401

from skills.produce_bootstrap import (
    append_report_reference_bootstrap,
    infer_report_reference_tier,
)


def test_infer_student_tier_from_message():
    assert (
        infer_report_reference_tier("给学生8b6d1125760bd3939b6e写一份13~15周的学情报告")
        == "student"
    )


def test_infer_class_tier():
    assert infer_report_reference_tier("生成 Class1 班级总览") == "class"


def test_append_reference_bootstrap_pins_student(tmp_path, monkeypatch):
    from skills.registry import SkillRegistry
    from skills.produce_bootstrap import messages_contain_reference_pin

    ref_dir = tmp_path / "report-writing" / "references"
    ref_dir.mkdir(parents=True)
    (ref_dir / "student.md").write_text("# Student ref\n", encoding="utf-8")
    monkeypatch.setenv("AGENT_SKILLS_DIR", str(tmp_path))

    messages: list = []
    loaded_refs: set[str] = set()
    ok = append_report_reference_bootstrap(
        messages,
        loaded_refs,
        user_message="给学生abc123456789012345678写学情报告",
        loaded_skills={"report-writing"},
    )
    assert ok
    assert "student" in loaded_refs
    assert messages_contain_reference_pin(messages, "student")
    tool_contents = [m.get("content") or "" for m in messages if m.get("role") == "tool"]
    assert any("Student ref" in c for c in tool_contents)

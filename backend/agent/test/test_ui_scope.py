import sys
from pathlib import Path

AGENT_ROOT = Path(__file__).resolve().parents[1]
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))

import runtime_bootstrap  # noqa: F401, E402

from data.filter_context import FilterContext, merge_http_context  # noqa: E402
from session.ui_scope import augment_user_message_with_ui_scope  # noqa: E402


def test_merge_http_context_keeps_selection_when_patch_only_classes():
    base = FilterContext(
        classes=("Class1",),
        selected_student_ids=("s1", "s2"),
        source="session",
    )
    incoming = FilterContext(
        week_range=(0, 15),
        source="http_body",
    )
    merged = merge_http_context(base, incoming)
    assert merged is not None
    assert merged.classes == ("Class1",)
    assert merged.selected_student_ids == ("s1", "s2")
    assert merged.week_range == (0, 15)


def test_augment_user_message_injects_selected_ids():
    fc = FilterContext(selected_student_ids=("a", "b", "c"), source="http_body")
    out = augment_user_message_with_ui_scope("让我看看我选的这几个学生表现如何", fc)
    assert "a, b, c" in out
    assert "勿再索要" in out


def test_augment_skips_without_selection_intent():
    fc = FilterContext(selected_student_ids=("a",), source="http_body")
    q = "全班平均分是多少"
    assert augment_user_message_with_ui_scope(q, fc) == q


def test_augment_already_selected_phrase():
    fc = FilterContext(selected_student_ids=("s1", "s2", "s3"), source="http_body")
    out = augment_user_message_with_ui_scope("我已经选择了三个学生了啊", fc)
    assert "s1" in out


def test_resolve_params_for_resource_strips_majors_on_student_info():
    fc = FilterContext(
        classes=("Class1",),
        majors=("J23517",),
        selected_student_ids=("a", "b"),
        source="http_body",
    )
    assert fc.resolve_params_for_resource("student_info") == {"student_ids": ["a", "b"]}
    assert "majors" not in fc.resolve_params_for_resource("student_info")
    submit = fc.resolve_params_for_resource("submit_record")
    assert submit.get("majors") == ["J23517"]
    assert submit.get("student_ids") == ["a", "b"]

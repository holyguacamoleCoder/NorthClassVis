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


def test_augment_user_message_no_longer_injects_into_text():
    """Scope is carried via filter_context / ui_scope chip, not user text."""
    fc = FilterContext(selected_student_ids=("a", "b", "c"), source="http_body")
    q = "让我看看我选的这几个学生表现如何"
    out = augment_user_message_with_ui_scope(q, fc)
    assert out == q
    assert "[系统·UI 同步]" not in out


def test_augment_large_selection_no_text_injection():
    ids = tuple(f"s{i}" for i in range(50))
    fc = FilterContext(selected_student_ids=ids, source="http_body")
    q = "分析我选的学生"
    assert augment_user_message_with_ui_scope(q, fc) == q


def test_augment_skips_without_selection_intent():
    fc = FilterContext(selected_student_ids=("a",), source="http_body")
    q = "全班平均分是多少"
    assert augment_user_message_with_ui_scope(q, fc) == q


def test_augment_already_selected_phrase_no_text_injection():
    fc = FilterContext(selected_student_ids=("s1", "s2", "s3"), source="http_body")
    q = "我已经选择了三个学生了啊"
    assert augment_user_message_with_ui_scope(q, fc) == q


def test_build_ui_scope_payload():
    from session.ui_scope import build_ui_scope_payload

    payload = build_ui_scope_payload(
        {
            "ui_scope": {
                "selected_student_ids": ["abc", ""],
                "classes": ["Class2"],
                "week_range": [10, 12],
            }
        }
    )
    assert payload == {
        "selected_student_ids": ["abc"],
        "classes": ["Class2"],
        "week_range": [10, 12],
    }


def test_build_ui_scope_payload_week_and_class_without_students():
    from session.ui_scope import build_ui_scope_payload

    payload = build_ui_scope_payload(
        {
            "ui_scope": {
                "selected_student_ids": [],
                "classes": ["Class1"],
                "week_range": [3, 8],
            }
        }
    )
    assert payload == {
        "classes": ["Class1"],
        "week_range": [3, 8],
    }
    assert build_ui_scope_payload({"ui_scope": {}}) is None
    assert build_ui_scope_payload({"ui_scope": {"selected_student_ids": []}}) is None


def test_build_ui_scope_payload_composer_extras():
    from session.ui_scope import build_ui_scope_payload, format_ui_scope_agent_hint

    payload = build_ui_scope_payload(
        {
            "ui_scope": {
                "knowledge_ids": ["链表"],
                "title_ids": ["t1"],
                "dataset": {"run_id": "r1", "dataset_id": "d1", "label": "基于 query_data"},
                "view_snapshot": {"view": "WeekView", "params": {"week_range": [1, 2]}},
                "report": {"path": "reports/overview.md", "label": "overview.md"},
            }
        }
    )
    assert payload["knowledge_ids"] == ["链表"]
    assert payload["title_ids"] == ["t1"]
    assert payload["dataset"]["run_id"] == "r1"
    assert payload["view_snapshot"]["view"] == "WeekView"
    assert payload["report"]["path"] == "reports/overview.md"
    hint = format_ui_scope_agent_hint(payload)
    assert hint is not None
    assert "知识点" in hint
    assert "dataset_id=d1" in hint
    assert "WeekView" in hint
    assert "overview.md" in hint
    # Extras-only still works without filter_context
    assert "本轮" in hint


def test_compose_llm_user_content_merges_single_user_message():
    from session.display import clean_user_content_for_display
    from session.ui_scope import compose_llm_user_content

    hint = "[系统·本轮范围] Class1\n\n--- 本轮分析范围 ---\n- 班级: Class1"
    merged = compose_llm_user_content("这批学生怎么样？", hint)
    assert merged.startswith("[系统·本轮范围]")
    assert "教师本轮问题：\n这批学生怎么样？" in merged
    assert clean_user_content_for_display(merged) == "这批学生怎么样？"
    assert compose_llm_user_content("只问一句", None) == "只问一句"


def test_drop_previous_ui_scope_hints_keeps_other_messages():
    from skills.message_meta import attach_ui_hidden_meta, drop_previous_ui_scope_hints
    from skills.tool_result import CONTENT_KIND_UI_SCOPE_HINT

    msgs = [
        {"role": "user", "content": "第一问"},
        {"role": "assistant", "content": "答1"},
        attach_ui_hidden_meta(
            {"role": "user", "content": "[系统·本轮范围] Class1"},
            content_kind=CONTENT_KIND_UI_SCOPE_HINT,
        ),
        {"role": "user", "content": "第二问"},
        {"role": "assistant", "content": "答2"},
        attach_ui_hidden_meta(
            {"role": "user", "content": "[系统·本轮范围] Class2"},
            content_kind=CONTENT_KIND_UI_SCOPE_HINT,
        ),
    ]
    kept = drop_previous_ui_scope_hints(msgs)
    assert len(kept) == 4
    assert all("[系统·本轮范围]" not in str(m.get("content") or "") for m in kept)
    assert kept[0]["content"] == "第一问"
    assert kept[-1]["content"] == "答2"


def test_clean_display_hides_ui_scope_from_legacy_text():
    from session.display import clean_user_content_for_display

    q = "只分析我选中的这些学生"
    legacy = (
        f"{q}\n\n"
        "[系统·UI 同步] 教师已在可视化面板选中学生，请直接用于 query_data / 分析：\n"
        "student_ID: a, b（共 2 人）"
    )
    assert clean_user_content_for_display(legacy) == q


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

"""Slim Nav scope in system prompt and get_current_filter_context."""

import json
import sys
from pathlib import Path

AGENT_ROOT = Path(__file__).resolve().parents[1]
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))

import runtime_bootstrap  # noqa: F401, E402

from common.prompts import format_filter_context_section  # noqa: E402
from common.system_prompt import SystemPromptBuilder, SystemPromptContext  # noqa: E402
from data.filter_context import FilterContext  # noqa: E402
from tools.handlers.context_tools import run_get_current_filter_context  # noqa: E402


def test_to_summary_dict_omits_bulk_ids():
    ids = tuple(f"id{i:02d}" for i in range(50))
    fc = FilterContext(classes=("Class1",), selected_student_ids=ids, source="http_body")
    summary = fc.to_summary_dict()
    assert summary["selected_student_count"] == 50
    assert summary.get("selected_student_ids") is None
    assert len(summary["selected_student_ids_preview"]) == 5
    assert summary.get("selected_student_ids_truncated") is True


def test_to_summary_dict_include_ids():
    fc = FilterContext(selected_student_ids=("a", "b"), source="http_body")
    full = fc.to_summary_dict(include_student_ids=True)
    assert full["selected_student_ids"] == ["a", "b"]


def test_to_summary_dict_includes_typical_student_ids(monkeypatch):
    repo_root = AGENT_ROOT.parent.parent
    monkeypatch.chdir(repo_root)
    fc = FilterContext(classes=("Class2",), week_range=(13, 15), source="http_body")
    summary = fc.to_summary_dict()
    typical = summary.get("typical_student_ids") or []
    assert len(typical) >= 2
    assert all(len(str(s)) >= 16 for s in typical)
    assert "week_view_hint" in summary


def test_format_filter_context_section_no_40_id_dump():
    fc = FilterContext(
        classes=("Class1",),
        majors=("J1", "J2"),
        week_range=(0, 15),
        selected_student_ids=tuple(f"s{i}" for i in range(96)),
        source="http_body",
    )
    text = format_filter_context_section(fc.to_summary_dict())
    assert "96 人" in text
    assert "s0, s1" not in text
    assert "s40" not in text
    assert "include_student_ids" in text
    assert "范围优先级" in text


def test_get_current_filter_context_default_summary():
    raw = run_get_current_filter_context(
        _filter_context=FilterContext(
            classes=("Class1",),
            selected_student_ids=("only-one",),
            source="http_body",
        ),
    )
    payload = json.loads(raw)
    assert payload["selected_student_count"] == 1
    assert payload.get("selected_student_ids") is None
    assert payload["selected_student_ids_preview"] == ["only-one"]


def test_get_current_filter_context_full_ids():
    raw = run_get_current_filter_context(
        include_student_ids=True,
        _filter_context=FilterContext(
            selected_student_ids=("a", "b"),
            source="http_body",
        ),
    )
    payload = json.loads(raw)
    assert payload["selected_student_ids"] == ["a", "b"]


def test_system_prompt_omits_dynamic_filter_scope():
    """Changing Nav must not rewrite the system prompt (prefix cache + history)."""
    fc = FilterContext(
        classes=("Class1",),
        selected_student_ids=tuple(f"x{i}" for i in range(30)),
        source="http_body",
    )
    prompt = SystemPromptBuilder().build(
        SystemPromptContext(permission_mode="analyze", filter_context=fc),
    )
    assert "30 人" not in prompt
    assert "本轮分析范围" not in prompt
    assert "get_current_filter_context" in prompt


def test_turn_scope_hint_includes_nav_and_extras():
    from session.ui_scope import format_turn_scope_hint

    fc = FilterContext(
        classes=("Class1",),
        week_range=(10, 12),
        selected_student_ids=("a", "b", "c"),
        source="http_body",
    )
    hint = format_turn_scope_hint(
        ui_scope={
            "knowledge_ids": ["链表"],
            "dataset": {"run_id": "r1", "label": "基于 query_data"},
        },
        filter_context=fc,
    )
    assert hint is not None
    assert "本轮" in hint
    assert "Class1" in hint
    assert "10–12" in hint or "10-12" in hint or "10" in hint
    assert "3 人" in hint
    assert "链表" in hint
    assert "run_id=r1" in hint


def test_format_datasets_catalog_section_and_prompt(tmp_path, monkeypatch):
    from common.prompts import SECTION_DATASETS_CATALOG, format_datasets_catalog_section
    from data.dataset_registry import DatasetRecord, append_dataset, format_catalog_hint

    monkeypatch.setattr(
        "data.dataset_registry.AGENT_STATE_DIR",
        tmp_path,
        raising=False,
    )
    append_dataset(
        "sess1",
        DatasetRecord(
            dataset_id="ds_aaa111bbb222",
            result_ref="query-results/x.json",
            user_turn=2,
            resource="submit_record",
            result_rows=40,
            query_limit=40,
        ),
    )
    hint = format_catalog_hint("sess1", tail=5)
    assert "ds_aaa111bbb222" in hint
    assert "result_ref=query-results/x.json" in hint
    section = format_datasets_catalog_section(hint)
    assert SECTION_DATASETS_CATALOG in section
    assert "dataset_id" in section or "ds_aaa111bbb222" in section

    prompt = SystemPromptBuilder().build(
        SystemPromptContext(permission_mode="analyze", session_id="sess1"),
    )
    assert SECTION_DATASETS_CATALOG in prompt
    assert "ds_aaa111bbb222" in prompt

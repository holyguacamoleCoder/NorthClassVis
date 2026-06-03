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


def test_system_prompt_uses_summary_scope():
    fc = FilterContext(
        classes=("Class1",),
        selected_student_ids=tuple(f"x{i}" for i in range(30)),
        source="http_body",
    )
    prompt = SystemPromptBuilder().build(
        SystemPromptContext(permission_mode="analyze", filter_context=fc),
    )
    assert "30 人" in prompt
    assert "x0, x1, x2, x3, x4" not in prompt

"""Nav panel scope yields to explicit query / teacher intent."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

import runtime_bootstrap  # noqa: F401, E402

AGENT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = AGENT_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from data.filter_context import FilterContext, nav_scope_suppressed_reason  # noqa: E402
from data.query import _apply_ui_student_selection  # noqa: E402
from loop_state import AnalysisToolContext  # noqa: E402
from tools.handlers.data_tools import run_query_data  # noqa: E402
from tools.runtime.data.inject import inject_data_tool_context  # noqa: E402


@pytest.fixture
def data_dir():
    return BACKEND_ROOT.parent / "data"


def test_nav_scope_suppressed_when_query_class_differs_from_panel():
    fc = FilterContext(
        classes=("Class1",),
        selected_student_ids=("5d89810b20079366fcc2", "8b6d1125760bd3939b6e"),
        majors=("J23517",),
        week_range=(13, 15),
        source="http_body",
    )
    reason = nav_scope_suppressed_reason(
        fc,
        {"class": "Class2"},
        teacher_message="Class2 第 13-15 周班级学情总览",
    )
    assert reason is not None
    merged = fc.merge_resolve_params(
        {"class": "Class2"},
        resource_id="week_aggregation",
        teacher_message="Class2 第 13-15 周班级学情总览",
    )
    assert "student_ids" not in merged
    assert merged.get("class") == "Class2"
    assert merged.get("week_range") == [13, 15]


def test_nav_scope_kept_when_teacher_mentions_selection():
    fc = FilterContext(
        classes=("Class2",),
        selected_student_ids=("6ae7d356ba998218af82", "2c6339f7c23a64d02081"),
        source="http_body",
    )
    reason = nav_scope_suppressed_reason(
        fc,
        {"class": "Class2"},
        teacher_message="帮我分析我选的这几个学生",
    )
    assert reason is None
    merged = fc.merge_resolve_params(
        {"class": "Class2"},
        resource_id="submit_record",
        teacher_message="帮我分析我选的这几个学生",
    )
    assert merged.get("student_ids") == [
        "6ae7d356ba998218af82",
        "2c6339f7c23a64d02081",
    ]


def test_query_class2_submit_record_ignores_class1_nav_students(data_dir, monkeypatch):
    """Reproduce session b99bab4ec9eb: Class2 submit_record must not be empty."""
    monkeypatch.chdir(BACKEND_ROOT.parent)
    fc = FilterContext(
        classes=("Class1",),
        selected_student_ids=("5d89810b20079366fcc2", "8b6d1125760bd3939b6e"),
        majors=("J23517", "J40192", "J57489", "J78901", "J87654"),
        week_range=(13, 15),
        source="http_body",
    )
    raw = run_query_data(
        resource="submit_record",
        **{"class": "Class2"},
        limit=0,
        _filter_context=fc,
        _teacher_message="Class2 第 13-15 周班级学情总览",
        data_dir=data_dir,
    )
    assert not raw.startswith("Error:")
    payload = json.loads(raw)
    meta = payload.get("meta") or {}
    assert meta.get("nav_scope_suppressed") is True
    assert meta.get("ui_selected_students") is None
    assert int(meta.get("rows_scanned") or 0) > 100


def test_nav_scope_suppressed_when_user_message_class_differs_from_query():
    fc = FilterContext(
        classes=("Class1",),
        selected_student_ids=("5d89810b20079366fcc2", "8b6d1125760bd3939b6e"),
        source="http_body",
    )
    reason = nav_scope_suppressed_reason(
        fc,
        {"class": "Class1"},
        teacher_message="Class2 这学期第 13 到 15 周整体学得怎么样",
    )
    assert reason is not None
    assert "Class2" in reason


def test_query_class2_ignores_class1_nav_students(data_dir, monkeypatch):
    monkeypatch.chdir(BACKEND_ROOT.parent)
    fc = FilterContext(
        classes=("Class1",),
        selected_student_ids=("5d89810b20079366fcc2", "8b6d1125760bd3939b6e"),
        week_range=(13, 15),
        source="http_body",
    )
    raw = run_query_data(
        resource="week_aggregation",
        classes=["Class2"],
        week_range=[13, 15],
        _filter_context=fc,
        _teacher_message="Class2 第 13-15 周班级学情总览",
        data_dir=data_dir,
    )
    assert not raw.startswith("Error:")
    payload = json.loads(raw)
    meta = payload.get("meta") or {}
    assert meta.get("nav_scope_suppressed") is True
    rows = payload.get("rows") or []
    student_ids = {row[0] for row in rows if row}
    assert len(student_ids) > 2

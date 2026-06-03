"""Tests for memory content classification (session vs cross-session)."""

import sys
from pathlib import Path

AGENT_ROOT = Path(__file__).resolve().parents[1]
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))

import runtime_bootstrap  # noqa: F401, E402

from common.memory_policy import is_session_scoped_content, session_scoped_memory_error  # noqa: E402


def test_rejects_student_report_delivery_note():
    text = (
        "- 学生8b6d1125760bd3939b6e的13~15周学情分析报告已生成，"
        "但包含的可视化面板未完全，需补全PortraitView和ScatterView。"
    )
    assert is_session_scoped_content(text) is True
    err = session_scoped_memory_error(text)
    assert err is not None
    assert err.startswith("Error:")


def test_allows_teacher_preference():
    text = "Class1 学情报告优先用表格，图表用折线不用饼图。"
    assert is_session_scoped_content(text) is False


def test_rejects_reports_path():
    assert is_session_scoped_content("See reports/student/foo/diagnosis.md for output") is True

"""UI transcript stays independent of LLM context compaction / injections."""

from __future__ import annotations

import sys
from pathlib import Path

AGENT_DIR = Path(__file__).resolve().parents[1]
if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))

from common.prompts import COMPACT_USER_MESSAGE_PREAMBLE  # noqa: E402
from session.display import (  # noqa: E402
    append_ui_turn,
    clean_user_content_for_display,
    ensure_ui_messages_seeded,
    extract_latest_turn_messages,
    messages_for_ui,
)
from session.models import ChatSession  # noqa: E402
from skills.message_meta import attach_ui_hidden_meta  # noqa: E402
from skills.tool_result import CONTENT_KIND_COMPACT_SUMMARY  # noqa: E402


def _session(**kwargs) -> ChatSession:
    return ChatSession(
        id="s1",
        title="t",
        permission_mode="analyze",
        created_at=1.0,
        updated_at=1.0,
        **kwargs,
    )


def test_clean_strips_ui_scope_and_reminder():
    raw = (
        "只分析我选中的学生\n\n"
        "[系统·UI 同步] 教师已在可视化面板选中学生，请直接用于 query_data / 分析：\n"
        "student_ID: a, b（共 2 人）"
        "<reminder>内部提示</reminder>"
    )
    assert clean_user_content_for_display(raw) == "只分析我选中的学生"

    merged = (
        "[系统·本轮范围] Class1\n\n"
        "--- 本轮分析范围 ---\n- 班级: Class1\n\n"
        "---\n教师本轮问题：\n"
        "继续问链表"
    )
    assert clean_user_content_for_display(merged) == "继续问链表"


def test_ui_transcript_survives_compaction_replacement():
    session = _session(
        messages=[
            {"role": "user", "content": "第一问"},
            {"role": "assistant", "content": "第一答"},
        ]
    )
    ensure_ui_messages_seeded(session)
    assert len(session.ui_messages) == 2

    # LLM context replaced by compact summary (as macro_compact does)
    session.messages = [
        attach_ui_hidden_meta(
            {
                "role": "user",
                "content": f"{COMPACT_USER_MESSAGE_PREAMBLE}\n\n摘要",
            },
            content_kind=CONTENT_KIND_COMPACT_SUMMARY,
        )
    ]
    # UI transcript unchanged
    assert [m["content"] for m in session.ui_messages] == ["第一问", "第一答"]
    assert len(messages_for_ui(session)) == 2


def test_append_ui_turn_uses_clean_user_text():
    session = _session(messages=[], ui_messages=[])
    turn = [
        {
            "role": "user",
            "content": (
                "只分析选中学生\n\n"
                "[系统·UI 同步] student_ID: x"
            ),
        },
        {"role": "assistant", "content": "好的"},
        {"role": "tool", "tool_call_id": "c1", "content": '{"rows":[]}'},
    ]
    append_ui_turn(
        session,
        display_user_text="只分析选中学生",
        turn_messages=turn,
        ui_scope={"selected_student_ids": ["abc123"]},
    )
    assert session.ui_messages[0]["content"] == "只分析选中学生"
    assert session.ui_messages[0]["ui_scope"]["selected_student_ids"] == ["abc123"]
    assert session.ui_messages[1]["content"] == "好的"
    assert session.ui_messages[2]["role"] == "tool"


def test_extract_latest_turn_after_compact_prefix():
    display = "继续分析 Class2"
    messages = [
        attach_ui_hidden_meta(
            {"role": "user", "content": f"{COMPACT_USER_MESSAGE_PREAMBLE}\n\nold"},
            content_kind=CONTENT_KIND_COMPACT_SUMMARY,
        ),
        {
            "role": "user",
            "content": f"{display}\n\n[系统·UI 同步] ids",
        },
        {"role": "assistant", "content": "ok"},
    ]
    turn = extract_latest_turn_messages(messages, display)
    assert turn[0]["role"] == "user"
    assert turn[-1]["content"] == "ok"

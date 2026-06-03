"""System prompt pinning for loaded skills and session todo plan."""

import sys
import tempfile
from pathlib import Path

AGENT_ROOT = Path(__file__).resolve().parents[1]
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))

from common.message import normalize_message
from common.prompts import SECTION_LOADED_NAMES, SECTION_SESSION_PLAN
from common.system_prompt import SystemPromptBuilder, SystemPromptContext
from context.config import ContextCompactConfig
from context.macro_compact import build_compacted_messages, extract_pinned_messages
from context.micro_compact import micro_compact_messages
from skills import SkillRegistry
from skills.message_meta import attach_pin_meta
from skills.tool_result import CONTENT_KIND_SKILL
from tools.handlers.todo_write import reset_todo_state, run_todo_write


def test_system_prompt_lists_loaded_skill_name_not_body(tmp_path):
    skill_dir = tmp_path / "skills"
    skill_dir.mkdir(parents=True)
    (skill_dir / "plan-a").mkdir()
    (skill_dir / "plan-a" / "SKILL.md").write_text(
        "---\nname: plan-a\ndescription: Plan A\n---\n\n## scope\nDo scope first.\n",
        encoding="utf-8",
    )
    registry = SkillRegistry(skills_dir=skill_dir)
    prompt = SystemPromptBuilder().build(
        SystemPromptContext(
            permission_mode="analyze",
            skills=registry,
            loaded_skills={"plan-a"},
            include_memory_guidance=False,
        )
    )
    assert SECTION_LOADED_NAMES in prompt
    assert "plan-a" in prompt
    assert "Do scope first." not in prompt


def test_system_prompt_includes_todo_plan():
    reset_todo_state()
    prompt = SystemPromptBuilder().build(
        SystemPromptContext(
            permission_mode="analyze",
            todo_items=[
                {
                    "content": "query Class1 majors",
                    "status": "in_progress",
                    "acceptance": "count_distinct by major",
                },
                {"content": "write report", "status": "pending"},
            ],
            include_memory_guidance=False,
        )
    )
    assert SECTION_SESSION_PLAN in prompt
    assert "query Class1 majors" in prompt
    assert "count_distinct by major" in prompt
    assert "Completed: 0/2" in prompt


def test_micro_compact_skips_pinned_load_skill_messages():
    config = ContextCompactConfig(keep_recent_tool_results=1, micro_compact_min_chars=50)
    pin_content = '✅ Skill "x" 已加载\n' + "a" * 200
    messages = [
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {"id": "c1", "name": "load_skill", "function": {"name": "load_skill"}},
                {"id": "c2", "name": "query_data", "function": {"name": "query_data"}},
                {"id": "c3", "name": "query_data", "function": {"name": "query_data"}},
            ],
        },
        attach_pin_meta(
            {"role": "tool", "tool_call_id": "c1", "content": pin_content},
            content_kind=CONTENT_KIND_SKILL,
            resource_id="x",
        ),
        {"role": "tool", "tool_call_id": "c2", "content": "b" * 200},
        {"role": "tool", "tool_call_id": "c3", "content": "c" * 200},
    ]
    n = micro_compact_messages(messages, config=config)
    assert n == 1
    assert messages[1]["content"].startswith('✅ Skill "x"')
    assert "Earlier tool result compacted" in messages[2]["content"]
    assert messages[3]["content"] == "c" * 200


def test_normalize_message_strips_agent_meta():
    messages = [
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "t1",
                    "type": "function",
                    "function": {"name": "load_skill", "arguments": '{"name":"demo"}'},
                }
            ],
        },
        attach_pin_meta(
            {"role": "tool", "tool_call_id": "t1", "content": "body"},
            content_kind=CONTENT_KIND_SKILL,
            resource_id="demo",
        ),
    ]
    out = normalize_message(messages)
    tool_msg = next(m for m in out if m.get("role") == "tool")
    assert "_agent_meta" not in tool_msg
    assert tool_msg["content"] == "body"


def test_build_compacted_messages_places_pinned_before_tail():
    pinned = [
        attach_pin_meta(
            {"role": "tool", "tool_call_id": "p1", "content": "skill body"},
            content_kind=CONTENT_KIND_SKILL,
            resource_id="rw",
        ),
    ]
    tail = [
        {"role": "assistant", "content": None, "tool_calls": [{"id": "t2"}]},
        {"role": "tool", "tool_call_id": "t2", "content": "data"},
    ]
    built = build_compacted_messages("summary", pinned=pinned, tail=tail)
    assert built[0]["role"] == "user"
    assert built[1]["content"] == "skill body"
    assert built[2]["role"] == "assistant"


def test_extract_pinned_messages():
    msgs = [
        {"role": "user", "content": "hi"},
        attach_pin_meta(
            {"role": "tool", "tool_call_id": "a", "content": "pin"},
            content_kind=CONTENT_KIND_SKILL,
            resource_id="s",
        ),
        {"role": "tool", "tool_call_id": "b", "content": "plain"},
    ]
    pinned = extract_pinned_messages(msgs)
    assert len(pinned) == 1
    assert pinned[0]["content"] == "pin"

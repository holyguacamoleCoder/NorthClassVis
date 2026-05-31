"""System prompt pinning for loaded skills and session todo plan."""

import sys
import tempfile
from pathlib import Path

AGENT_ROOT = Path(__file__).resolve().parents[1]
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))

from common.prompts import SECTION_LOADED_SKILLS, SECTION_SESSION_PLAN
from common.system_prompt import SystemPromptBuilder, SystemPromptContext
from skills import SkillRegistry
from tools.handlers.todo_write import reset_todo_state, run_todo_write


def test_system_prompt_includes_loaded_skill_body(tmp_path):
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
    assert SECTION_LOADED_SKILLS in prompt
    assert "## scope" in prompt
    assert "Do scope first." in prompt


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


def test_micro_compact_skips_load_skill_messages():
    from context.config import ContextCompactConfig
    from context.micro_compact import micro_compact_messages

    config = ContextCompactConfig(keep_recent_tool_results=1, micro_compact_min_chars=50)
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
        {"role": "tool", "tool_call_id": "c1", "content": "[Skill loaded: x]\n" + "a" * 200},
        {"role": "tool", "tool_call_id": "c2", "content": "b" * 200},
        {"role": "tool", "tool_call_id": "c3", "content": "c" * 200},
    ]
    n = micro_compact_messages(messages, config=config)
    assert n == 1
    assert messages[1]["content"].startswith("[Skill loaded:")
    assert "Earlier tool result compacted" in messages[2]["content"]
    assert messages[3]["content"] == "c" * 200

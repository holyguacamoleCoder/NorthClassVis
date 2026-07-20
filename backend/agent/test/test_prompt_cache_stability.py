"""Prefix-cache contracts: system must stay byte-stable within a permission mode."""

from __future__ import annotations

import sys
from pathlib import Path

AGENT_ROOT = Path(__file__).resolve().parents[1]
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))

from common.system_prompt import SystemPromptBuilder, SystemPromptContext


def test_system_prompt_stable_across_volatile_session_state():
    b = SystemPromptBuilder()
    base = b.build(SystemPromptContext(permission_mode="analyze"))
    volatile = b.build(
        SystemPromptContext(
            permission_mode="analyze",
            todo_items=[{"content": "q", "status": "in_progress"}],
            loaded_skills={"data-exploration"},
            loaded_references={"class"},
            modify_context={
                "parent_run_id": "r1",
                "strategy": "requery",
                "patch": {},
            },
            session_id="sess-cache-test",
        )
    )
    assert base == volatile, (
        "system must be byte-stable within mode; "
        "put volatile state in turn user / tool results"
    )


def test_system_prompt_may_differ_across_modes():
    b = SystemPromptBuilder()
    a = b.build(SystemPromptContext(permission_mode="analyze"))
    p = b.build(SystemPromptContext(permission_mode="produce"))
    assert a != p

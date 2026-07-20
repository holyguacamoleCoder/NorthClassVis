"""Unified assembly of the agent system prompt."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from common.memory import MemoryManager, get_memory_manager
from common.prompts import (
    MEMORY_GUIDANCE,
    build_base_agent_prompt,
    format_permission_mode,
    format_session_section,
    format_skills_section,
)

if TYPE_CHECKING:
    from data.filter_context import FilterContext
    from skills.registry import SkillRegistry


@dataclass
class SystemPromptContext:
    """Runtime inputs that shape the system prompt for one turn.

    Volatile session state (todo / datasets / deliverables / modify / loaded
    skill names / Nav filter) must NOT be passed into ``build`` for injection:
    put those in the current-turn user hint or tool-result snapshots so the
    system prefix stays cache-stable within a permission mode.

    Legacy fields below are kept for call-site compatibility but are ignored
    by ``build`` (prefix cache).
    """

    permission_mode: str = "consult"
    session_context: list[str] = field(default_factory=list)
    filter_context: "FilterContext | None" = None
    skills: SkillRegistry | None = None
    loaded_skills: set[str] | list[str] = field(default_factory=list)
    loaded_references: set[str] | list[str] = field(default_factory=list)
    todo_items: list[dict[str, str]] = field(default_factory=list)
    session_id: str | None = None
    modify_context: dict | None = None
    include_memory_guidance: bool = True


class SystemPromptBuilder:
    """
    Compose the system prompt from static templates, persisted memories,
    and mode/skills catalog — intentionally excluding per-turn volatile state.
    """

    def __init__(self, memory: MemoryManager | None = None):
        self.memory = memory or get_memory_manager()

    def build(self, ctx: SystemPromptContext | None = None) -> str:
        ctx = ctx or SystemPromptContext()
        # Stable within mode: base + optional durable memory + permission +
        # optional hooks session blocks + skills catalog + memory guidance.
        # filter_context / todo / datasets / deliverables / modify / loaded
        # names are injected via turn user hints or tool results (prefix cache).
        parts: list[str] = [build_base_agent_prompt(ctx.permission_mode).strip()]

        memory_section = self.memory.load_memory_prompt()
        if memory_section:
            parts.append(memory_section)

        parts.append(format_permission_mode(ctx.permission_mode))

        if ctx.include_memory_guidance:
            parts.append(MEMORY_GUIDANCE.strip())

        if ctx.session_context:
            parts.append(format_session_section(ctx.session_context))

        if ctx.skills is not None:
            parts.append(format_skills_section(ctx.skills.describe_available()))

        return "\n\n".join(parts)

    def reload_memories(self) -> int:
        """Refresh memories from disk (e.g. after save_memory in the same session)."""
        return self.memory.load_all()


_default_builder: SystemPromptBuilder | None = None


def get_system_prompt_builder() -> SystemPromptBuilder:
    global _default_builder
    if _default_builder is None:
        _default_builder = SystemPromptBuilder()
    return _default_builder

"""Unified assembly of the agent system prompt."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from common.memory import MemoryManager, get_memory_manager
from common.prompts import (
    BASE_AGENT_PROMPT,
    MEMORY_GUIDANCE,
    format_filter_context_section,
    format_permission_mode,
    format_session_section,
    format_skills_section,
)

if TYPE_CHECKING:
    from data.filter_context import FilterContext
    from skills.registry import SkillRegistry


@dataclass
class SystemPromptContext:
    """Runtime inputs that shape the system prompt for one turn."""

    permission_mode: str = "consult"
    session_context: list[str] = field(default_factory=list)
    filter_context: "FilterContext | None" = None
    skills: SkillRegistry | None = None
    include_memory_guidance: bool = True


class SystemPromptBuilder:
    """
    Compose the full system prompt from static templates (prompts.py),
    persisted memories, and runtime context (mode, hooks, skills).
    """

    def __init__(self, memory: MemoryManager | None = None):
        self.memory = memory or get_memory_manager()

    def build(self, ctx: SystemPromptContext | None = None) -> str:
        ctx = ctx or SystemPromptContext()
        parts: list[str] = [BASE_AGENT_PROMPT.strip()]

        memory_section = self.memory.load_memory_prompt()
        if memory_section:
            parts.append(memory_section)

        parts.append(format_permission_mode(ctx.permission_mode))

        if ctx.session_context:
            parts.append(format_session_section(ctx.session_context))

        if ctx.filter_context is not None:
            parts.append(format_filter_context_section(ctx.filter_context.to_dict()))

        if ctx.skills is not None:
            parts.append(format_skills_section(ctx.skills.describe_available()))

        if ctx.include_memory_guidance:
            parts.append(MEMORY_GUIDANCE.strip())

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

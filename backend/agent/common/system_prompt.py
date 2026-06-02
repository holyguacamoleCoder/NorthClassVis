"""Unified assembly of the agent system prompt."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from common.memory import MemoryManager, get_memory_manager
from common.prompts import (
    MEMORY_GUIDANCE,
    build_base_agent_prompt,
    format_filter_context_section,
    format_loaded_skill_names_section,
    format_permission_mode,
    format_session_plan_section,
    format_session_section,
    format_skills_section,
)
from skills.registry import _resolve_skill_name

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
    loaded_skills: set[str] | list[str] = field(default_factory=list)
    loaded_references: set[str] | list[str] = field(default_factory=list)
    todo_items: list[dict[str, str]] = field(default_factory=list)
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
        parts: list[str] = [build_base_agent_prompt(ctx.permission_mode).strip()]

        memory_section = self.memory.load_memory_prompt()
        if memory_section:
            parts.append(memory_section)

        parts.append(format_permission_mode(ctx.permission_mode))

        if ctx.session_context:
            parts.append(format_session_section(ctx.session_context))

        if ctx.filter_context is not None:
            parts.append(format_filter_context_section(ctx.filter_context.to_summary_dict()))

        if ctx.skills is not None:
            parts.append(format_skills_section(ctx.skills.describe_available()))

        loaded_skill_names = {
            _resolve_skill_name(str(n)) for n in (ctx.loaded_skills or []) if str(n).strip()
        }
        if (ctx.permission_mode or "").strip().lower() == "produce":
            loaded_skill_names.add("report-writing")
        loaded_ref_names = {str(n).strip() for n in (ctx.loaded_references or []) if str(n).strip()}
        names_block = format_loaded_skill_names_section(
            loaded_skill_names,
            loaded_ref_names,
        )
        if names_block:
            parts.append(names_block)

        plan_block = format_session_plan_section(ctx.todo_items)
        if plan_block:
            parts.append(plan_block)

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

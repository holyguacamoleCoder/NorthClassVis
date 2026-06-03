from skills import get_registry
from skills.registry import _resolve_skill_name
from skills.tool_result import (
    default_skill_references_hint,
    format_skill_active_result,
    format_skill_load_result,
)

# Fallback for direct unit tests that do not pass _loaded_skills.
_FALLBACK_LOADED: set[str] = set()


def run_load_skill(
    name: str | None = None,
    *,
    _loaded_skills: set[str] | None = None,
) -> str:
    loaded = _loaded_skills if _loaded_skills is not None else _FALLBACK_LOADED
    if not name or not str(name).strip():
        return (
            "Error: skill name is required | Next: pick a skill id from the "
            "available skills list in the system prompt."
        )
    raw_name = str(name).strip()
    skill_name = _resolve_skill_name(raw_name)
    if skill_name in loaded or raw_name in loaded:
        return format_skill_active_result(skill_name)

    registry = get_registry()
    document = registry.documents.get(skill_name)
    if document is None:
        return registry.load_full_text(skill_name)

    loaded.add(skill_name)
    skill_xml = registry.load_full_text(skill_name)
    hint = default_skill_references_hint() if skill_name == "report-writing" else None
    return format_skill_load_result(skill_name, skill_xml, references_hint=hint)

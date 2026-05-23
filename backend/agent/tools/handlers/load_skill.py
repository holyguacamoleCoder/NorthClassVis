from skills import get_registry

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
    skill_name = str(name).strip()
    if skill_name in loaded:
        return (
            f"Skill '{skill_name}' is already loaded in this session context. "
            "Use query_data / aggregate_data directly unless you need another skill."
        )
    content = get_registry().load_full_text(skill_name)
    if not content.startswith("Error:"):
        loaded.add(skill_name)
        return f"[Skill loaded: {skill_name}]\n{content}"
    return content

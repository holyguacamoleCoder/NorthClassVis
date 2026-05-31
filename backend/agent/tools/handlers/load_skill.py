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
            f"[Skill active: {skill_name}] Full instructions are in the system prompt "
            "section 「已加载技能」 on every model turn. Proceed with query_data / "
            "aggregate_data, or load_skill another name if needed."
        )
    document = get_registry().documents.get(skill_name)
    if document is None:
        return get_registry().load_full_text(skill_name)
    loaded.add(skill_name)
    return (
        f"[Skill loaded: {skill_name}] Workflow is pinned in the system prompt "
        "section 「已加载技能」 on every following turn (not only this tool message). "
        "Follow that section for steps, sections, and report paths."
    )

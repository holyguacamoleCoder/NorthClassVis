from skills import get_registry

_LOADED_SKILLS: set[str] = set()


def run_load_skill(name: str | None) -> str:
    if not name or not str(name).strip():
        return "Error: skill name is required"
    skill_name = str(name).strip()
    if skill_name in _LOADED_SKILLS:
        return (
            f"Skill '{skill_name}' is already loaded in this session context. "
            "Use query_data / aggregate_data directly unless you need another skill."
        )
    content = get_registry().load_full_text(skill_name)
    if not content.startswith("Error:"):
        _LOADED_SKILLS.add(skill_name)
    return content

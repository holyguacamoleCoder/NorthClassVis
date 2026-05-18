from skills import get_registry


def run_load_skill(name: str | None) -> str:
    if not name or not str(name).strip():
        return "Error: skill name is required"
    return get_registry().load_full_text(str(name).strip())

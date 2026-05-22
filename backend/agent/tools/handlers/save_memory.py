"""save_memory tool — persist cross-session agent memories."""

from common.memory import get_memory_manager


def run_save_memory(name: str, description: str, mem_type: str, content: str) -> str:
    result = get_memory_manager().save_memory(name, description, mem_type, content)
    get_memory_manager().load_all()
    return result

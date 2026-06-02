"""memory tool — rolling journals (user | memory) with add/replace/remove."""

from common.memory import get_memory_manager


def run_memory(
    action: str,
    target: str,
    content: str = "",
    old_text: str = "",
) -> str:
    mgr = get_memory_manager()
    result = mgr.apply_memory(action, target, content=content, old_text=old_text)
    mgr.load_all()
    return result

def prepend_hook_messages(content: str, messages: list[str]) -> str:
    if not messages:
        return content
    prefix = "\n".join(f"[Hook message]: {m}" for m in messages)
    if content:
        return f"{prefix}\n\n{content}"
    return prefix


def append_hook_notes(content: str, messages: list[str]) -> str:
    if not messages:
        return content
    notes = "\n".join(f"[Hook note]: {m}" for m in messages)
    if content:
        return f"{content}\n{notes}"
    return notes

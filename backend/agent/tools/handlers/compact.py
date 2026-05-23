def run_compact(focus: str | None = None) -> str:
    """Placeholder; AgentLoop applies macro compaction and rewrites this result."""
    focus_bit = f"focus={focus!r}" if focus else "focus=(none)"
    return (
        "[Compact pending: macro compaction runs in AgentLoop after this tool call] "
        f"{focus_bit}"
    )


def format_compact_applied_result(
    *,
    applied: bool,
    messages_before: int = 0,
    messages_after: int = 0,
    tail_turns: int = 0,
    focus: str | None = None,
    recent_files: list[str] | None = None,
    reason: str | None = None,
) -> str:
    if not applied:
        hint = reason or "compaction_disabled"
        return (
            f"[Compact skipped: {hint}] "
            "Automatic micro/macro compaction may still run each turn when enabled."
        )
    lines = [
        "[Compact applied: macro summary + recent tail turns]",
        f"messages: {messages_before} → {messages_after} (tail_turns={tail_turns})",
    ]
    if focus:
        lines.append(f"focus: {focus}")
    if recent_files:
        lines.append(f"recent_files: {', '.join(recent_files)}")
    lines.append(
        "Earlier tool details may be summarized; re-run query_data if you need full TabularResult."
    )
    return "\n".join(lines)

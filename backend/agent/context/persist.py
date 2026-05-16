from pathlib import Path

from .config import ContextCompactConfig, DATA_DIR, DEFAULT_CONFIG

PERSISTED_MARKER_START = "<persisted-output>"
COMPACTED_TOOL_PLACEHOLDER = (
    "[Earlier tool result compacted. Re-run the tool if you need full detail.]"
)


def maybe_persist_output(
    tool_call_id: str,
    output: str,
    *,
    config: ContextCompactConfig = DEFAULT_CONFIG,
) -> str:
    # 对于过长的工具输出，进行持久化，前端返回预览
    if not config.enabled or len(output) <= config.persist_threshold:
        return output

    config.tool_results_dir.mkdir(parents=True, exist_ok=True)
    stored_path = config.tool_results_dir / f"{tool_call_id}.txt"
    if not stored_path.exists():
        stored_path.write_text(output, encoding="utf-8")

    preview = output[: config.preview_chars]
    try:
        rel_path = stored_path.relative_to(DATA_DIR)
    except ValueError:
        rel_path = stored_path

    return (
        f"{PERSISTED_MARKER_START}\n"
        f"Full output saved to: {rel_path.as_posix()}\n"
        "Preview:\n"
        f"{preview}\n"
        "</persisted-output>"
    )

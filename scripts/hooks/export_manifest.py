#!/usr/bin/env python3
"""PostToolUse (write_file): append one line to data/exports/manifest.jsonl."""

from __future__ import annotations

from _lib import (
    EXPORT_MANIFEST,
    append_jsonl,
    hook_event,
    hook_tool_input,
    hook_tool_name,
    normalize_data_path,
    utc_now,
)


def main() -> None:
    if hook_event() != "PostToolUse" or hook_tool_name() != "write_file":
        return

    inp = hook_tool_input()
    path = normalize_data_path(str(inp.get("path") or ""))
    if not path.startswith("exports/") and not path.startswith("exports"):
        return
    if path == "exports" or path == "exports/":
        return

    content = inp.get("content")
    size = len(content) if isinstance(content, str) else None

    append_jsonl(
        EXPORT_MANIFEST,
        {
            "ts": utc_now(),
            "event": "write_file",
            "path": path,
            "bytes": size,
        },
    )


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""PreToolUse (read_file): append read audit log; soft hint when scanning raw CSV without limit."""

from __future__ import annotations

import sys

from _lib import (
    READ_AUDIT_LOG,
    append_jsonl,
    hook_event,
    hook_tool_input,
    hook_tool_name,
    is_sensitive_source,
    utc_now,
)


def main() -> None:
    if hook_event() != "PreToolUse" or hook_tool_name() != "read_file":
        return

    inp = hook_tool_input()
    path = str(inp.get("path") or "")
    limit = inp.get("limit")

    append_jsonl(
        READ_AUDIT_LOG,
        {
            "ts": utc_now(),
            "event": "read_file",
            "path": path,
            "limit": limit,
            "sensitive": is_sensitive_source(path),
        },
    )

    if is_sensitive_source(path) and limit is None:
        sys.stderr.write(
            "Tip: reading a raw dataset without `limit` may be slow and costly. "
            "Consider limit=50 for exploration, or aggregate in exports/ first."
        )
        sys.exit(2)


if __name__ == "__main__":
    main()

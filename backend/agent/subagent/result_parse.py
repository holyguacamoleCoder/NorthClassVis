"""Parse run_subagent tool result text into structured fields."""

from __future__ import annotations

import re
from typing import Any


def parse_subagent_tool_result(content: str) -> dict[str, Any]:
    text = (content or "").strip()
    out: dict[str, Any] = {
        "ok": False,
        "kind": "",
        "turns": 0,
        "refs": [],
        "dataset_ids": [],
        "summary": "",
        "error": None,
    }
    if not text:
        return out

    header = re.match(
        r"\[SubAgent\s+(\S+)\s+(OK|FAIL)\]",
        text,
        re.IGNORECASE,
    )
    if header:
        out["kind"] = header.group(1)
        out["ok"] = header.group(2).upper() == "OK"

    turns = re.search(r"^turns:\s*(\d+)", text, re.MULTILINE)
    if turns:
        out["turns"] = int(turns.group(1))

    section = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped == "refs:":
            section = "refs"
            continue
        if stripped == "dataset_ids:":
            section = "dataset_ids"
            continue
        if stripped == "summary:":
            section = "summary"
            continue
        if stripped.startswith("error:"):
            out["error"] = stripped[6:].strip()
            section = None
            continue
        if section == "refs" and stripped.startswith("- "):
            out["refs"].append(stripped[2:].strip())
        elif section == "dataset_ids" and stripped.startswith("- "):
            out["dataset_ids"].append(stripped[2:].strip())
        elif section == "summary":
            if stripped and stripped != "(empty)":
                out["summary"] = (
                    f"{out['summary']}\n{stripped}".strip()
                    if out["summary"]
                    else stripped
                )

    return out

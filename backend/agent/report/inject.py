from __future__ import annotations

import json
import re
from typing import Any

from .charts import _link_key, extract_chart_blocks

_FORBID_INJECT = frozenset({"StudentView"})


def inject_report_charts_from_links(
    source: str,
    session_links: list[dict[str, Any]] | None,
) -> tuple[str, list[str]]:
    """
    Insert missing ```report-chart``` blocks from session build_visual_links.

    Returns (new_markdown, notes).
    """
    if not session_links:
        return source, []

    existing_keys = {
        _link_key(b.view, b.params)
        for b in extract_chart_blocks(source)
        if b.view and not b.error
    }
    to_inject: list[dict[str, Any]] = []
    for link in session_links:
        if not isinstance(link, dict):
            continue
        view = link.get("view")
        params = link.get("params") if isinstance(link.get("params"), dict) else {}
        if not view or view in _FORBID_INJECT:
            continue
        key = _link_key(str(view), params)
        if key in existing_keys:
            continue
        to_inject.append({"view": view, "params": params})
        existing_keys.add(key)

    if not to_inject:
        return source, []

    blocks: list[str] = []
    notes: list[str] = []
    for link in to_inject:
        view = str(link["view"])
        payload = json.dumps(
            {"view": view, "params": link.get("params") or {}},
            ensure_ascii=False,
            indent=2,
        )
        blocks.append(f"```report-chart\n{payload}\n```")
        notes.append(f"auto-injected report-chart for {view}")

    insert_text = "\n\n".join(blocks) + "\n\n"
    text = source or ""
    lowered = text.lower()
    for marker in ("## evidence", "## limitations"):
        idx = lowered.find(marker)
        if idx >= 0:
            return text[:idx] + insert_text + text[idx:], notes
    return text.rstrip() + "\n\n" + insert_text, notes

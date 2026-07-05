from __future__ import annotations

import json
import re
from typing import Any

# Wrong: ![alt](<report-chart>{...}) or (<report-chart>{...})
_WRONG_CHART_IMAGE_RE = re.compile(
    r"!\[[^\]]*\]\(\s*<report-chart>\s*(\{[\s\S]*?\})\s*\)",
    re.IGNORECASE,
)
_WRONG_CHART_PAREN_RE = re.compile(
    r"\(\s*<report-chart>\s*(\{[\s\S]*?\})\s*\)",
    re.IGNORECASE,
)


def _payload_to_fence(payload_raw: str) -> str | None:
    try:
        obj = json.loads(payload_raw.strip())
    except json.JSONDecodeError:
        return None
    if not isinstance(obj, dict):
        return None
    formatted = json.dumps(obj, ensure_ascii=False, indent=2)
    return f"```report-chart\n{formatted}\n```"


def fix_wrong_report_chart_syntax(source: str) -> tuple[str, list[str]]:
    """Convert invalid <report-chart> embeds to fenced blocks."""
    notes: list[str] = []
    text = source or ""

    def _sub_image(match: re.Match[str]) -> str:
        fence = _payload_to_fence(match.group(1))
        if fence:
            notes.append("fixed image-style report-chart embed")
            return fence
        return match.group(0)

    def _sub_paren(match: re.Match[str]) -> str:
        fence = _payload_to_fence(match.group(1))
        if fence:
            notes.append("fixed parenthesis report-chart embed")
            return fence
        return match.group(0)

    text = _WRONG_CHART_IMAGE_RE.sub(_sub_image, text)
    text = _WRONG_CHART_PAREN_RE.sub(_sub_paren, text)
    return text, notes


def find_wrong_report_chart_syntax(source: str) -> list[str]:
    """Errors for validate when fix did not run or pattern remains."""
    errors: list[str] = []
    if _WRONG_CHART_IMAGE_RE.search(source or ""):
        errors.append(
            "invalid chart syntax: use ```report-chart\\n{...}\\n``` fence, "
            "not ![alt](<report-chart>{...})"
        )
    if _WRONG_CHART_PAREN_RE.search(source or ""):
        errors.append(
            "invalid chart syntax: use ```report-chart fence, not (<report-chart>{...})"
        )
    return errors

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from common.paths import PROJECT_ROOT
from data.visual_links import validate_links

_META_DIR = PROJECT_ROOT / "data" / "meta"
_DEFAULT_PROTOCOL_PATH = _META_DIR / "report_chart_protocol.yaml"

_CHART_FENCE_RE = re.compile(
    r"```(?:report-chart|chart|json)\s*\r?\n([\s\S]*?)```",
    re.IGNORECASE,
)


@lru_cache(maxsize=1)
def _load_protocol_cached(path_str: str) -> dict[str, Any]:
    with Path(path_str).open(encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def load_chart_protocol(protocol_path: Path | None = None) -> dict[str, Any]:
    path = protocol_path or _DEFAULT_PROTOCOL_PATH
    return _load_protocol_cached(str(path.resolve()))


@dataclass
class ChartBlock:
    index: int
    view: str | None
    params: dict[str, Any]
    raw: str
    error: str | None = None


@dataclass
class ChartValidation:
    blocks: list[ChartBlock] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def extract_chart_blocks(source: str) -> list[ChartBlock]:
    blocks: list[ChartBlock] = []
    for idx, match in enumerate(_CHART_FENCE_RE.finditer(source or "")):
        raw = match.group(1).strip()
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError as exc:
            blocks.append(
                ChartBlock(index=idx, view=None, params={}, raw=raw, error=str(exc))
            )
            continue
        if not isinstance(obj, dict):
            blocks.append(
                ChartBlock(
                    index=idx,
                    view=None,
                    params={},
                    raw=raw,
                    error="chart payload must be a JSON object",
                )
            )
            continue
        view = obj.get("view") or obj.get("panel")
        params = obj.get("params") if isinstance(obj.get("params"), dict) else {}
        blocks.append(
            ChartBlock(
                index=idx,
                view=str(view) if view else None,
                params=params,
                raw=raw,
                error=None if view else "missing view field",
            )
        )
    return blocks


def validate_report_charts(
    source: str,
    *,
    protocol_path: Path | None = None,
) -> ChartValidation:
    protocol = load_chart_protocol(protocol_path)
    limits = protocol.get("limits") or {}
    max_per_view: dict[str, int] = dict(limits.get("max_per_view") or {})
    forbid: set[str] = {str(v) for v in (limits.get("forbid_report_chart") or [])}

    result = ChartValidation()
    blocks = extract_chart_blocks(source)
    result.blocks = blocks
    view_counts: dict[str, int] = {}

    links: list[dict[str, Any]] = []
    for block in blocks:
        if block.error:
            result.errors.append(f"report-chart block {block.index + 1}: {block.error}")
            continue
        view = block.view or "?"
        view_counts[view] = view_counts.get(view, 0) + 1
        if view in forbid:
            result.errors.append(
                f"report-chart block {block.index + 1}: {view} must not use report-chart fence"
            )
        links.append({"view": block.view, "params": block.params})

    for view, count in view_counts.items():
        cap = max_per_view.get(view)
        if cap is not None and count > cap:
            result.errors.append(f"{view}: at most {cap} report-chart block(s), found {count}")

    if links:
        payload = validate_links(links)
        for item in payload.get("rejected") or []:
            if isinstance(item, dict):
                result.errors.append(
                    f"{item.get('view', '?')}: {item.get('reason', 'invalid')}"
                )
        for warn in payload.get("warnings") or []:
            result.warnings.append(str(warn))

    return result


def _link_key(view: str | None, params: dict[str, Any]) -> str:
    return json.dumps({"view": view, "params": params}, sort_keys=True, ensure_ascii=False)


def validate_charts_against_session(
    source: str,
    session_links: list[dict[str, Any]] | None,
) -> list[str]:
    """Warn when report-chart params were not validated via build_visual_links this session."""
    blocks = [b for b in extract_chart_blocks(source) if b.view and not b.error]
    if not blocks:
        return []
    if not session_links:
        return [
            "report-chart present but no build_visual_links in session; params unverified"
        ]
    session_keys = {
        _link_key(str(item.get("view")), item.get("params") or {})
        for item in session_links
        if isinstance(item, dict) and item.get("view")
    }
    issues: list[str] = []
    for block in blocks:
        key = _link_key(block.view, block.params)
        if key not in session_keys:
            issues.append(
                f"report-chart {block.view} params not in session build_visual_links "
                "(call build_visual_links with same params before write)"
            )
    return issues


def check_chart_explanations(
    source: str,
    *,
    min_lines: int = 2,
) -> list[str]:
    """Require non-empty prose lines after each report-chart fence."""
    protocol = load_chart_protocol()
    limits = protocol.get("limits") or {}
    required = int(limits.get("require_explanation_lines_below") or min_lines)
    warnings: list[str] = []
    for match in _CHART_FENCE_RE.finditer(source or ""):
        after = source[match.end() :]
        lines: list[str] = []
        for line in after.splitlines():
            stripped = line.strip()
            if stripped.startswith("##"):
                break
            if stripped.startswith("```"):
                break
            if stripped:
                lines.append(stripped)
            if len(lines) >= required:
                break
        if len(lines) < required:
            warnings.append(
                f"report-chart block {match.start()}: need >={required} explanation line(s) below"
            )
    return warnings

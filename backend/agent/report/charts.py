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

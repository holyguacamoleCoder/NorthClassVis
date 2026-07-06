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

from .normalize import find_wrong_report_chart_syntax

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


def parse_chart_fence_body(raw: str) -> tuple[dict[str, Any] | None, str, str | None]:
    """
    Parse the first JSON object inside a fence body.

    Returns (obj, trailing_prose, error). trailing_prose is non-empty when agents
    paste explanation lines inside the fence (common cause of Extra data).
    """
    text = (raw or "").strip()
    if not text:
        return None, "", "empty chart fence"
    decoder = json.JSONDecoder()
    try:
        obj, end = decoder.raw_decode(text)
    except json.JSONDecodeError as exc:
        return None, "", str(exc)
    trailing = text[end:].strip()
    if not isinstance(obj, dict):
        return None, trailing, "chart payload must be a JSON object"
    return obj, trailing, None


def extract_chart_blocks(source: str) -> list[ChartBlock]:
    blocks: list[ChartBlock] = []
    for idx, match in enumerate(_CHART_FENCE_RE.finditer(source or "")):
        raw = match.group(1).strip()
        obj, trailing, err = parse_chart_fence_body(raw)
        if err:
            blocks.append(
                ChartBlock(index=idx, view=None, params={}, raw=raw, error=err)
            )
            continue
        if trailing:
            blocks.append(
                ChartBlock(
                    index=idx,
                    view=None,
                    params={},
                    raw=raw,
                    error=(
                        "chart fence must contain only JSON; "
                        f"move trailing text outside the fence: {trailing[:60]!r}…"
                        if len(trailing) > 60
                        else f"chart fence must contain only JSON; "
                        f"move trailing text outside: {trailing!r}"
                    ),
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
    result.errors.extend(find_wrong_report_chart_syntax(source))
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


def _chart_block_score(view: str, params: dict[str, Any]) -> int:
    """Prefer blocks with richer params when deduping (e.g. WeekView + student_ids)."""
    score = 0
    if view == "WeekView" and params.get("student_ids"):
        score += 10
    if view == "QuestionView" and params.get("title_ids"):
        score += len(params.get("title_ids") or [])
    return score


def repair_report_chart_fences(source: str) -> tuple[str, list[str]]:
    """
    Move trailing prose out of ```report-chart``` fences; normalize JSON body.
    """
    notes: list[str] = []

    def _repair(match: re.Match[str]) -> str:
        raw = match.group(1)
        obj, trailing, err = parse_chart_fence_body(raw)
        if err or not obj:
            return match.group(0)
        if not trailing:
            formatted = json.dumps(obj, ensure_ascii=False, indent=2)
            if formatted.strip() == raw.strip():
                return match.group(0)
            notes.append(f"normalized report-chart JSON for {obj.get('view', '?')}")
            return f"```report-chart\n{formatted}\n```"
        view = obj.get("view") or "?"
        formatted = json.dumps(obj, ensure_ascii=False, indent=2)
        notes.append(
            f"moved trailing text out of report-chart fence ({view})"
        )
        return f"```report-chart\n{formatted}\n```\n\n{trailing}"

    text = _CHART_FENCE_RE.sub(_repair, source or "")
    return text, notes


def sync_report_chart_week_view_params(
    source: str,
    session_links: list[dict[str, Any]] | None,
) -> tuple[str, list[str]]:
    """Replace placeholder WeekView student_ids in report-chart with session link params."""
    if not session_links:
        return source, []

    from data.filter_context import clean_student_ids, is_placeholder_student_id

    week_links = [
        link
        for link in session_links
        if link.get("view") == "WeekView" and isinstance(link.get("params"), dict)
    ]
    if not week_links:
        return source, []

    canonical = week_links[-1].get("params") or {}
    canon_ids = clean_student_ids(canonical.get("student_ids") or [])
    if not canon_ids:
        return source, []

    canon_wr = canonical.get("week_range")
    notes: list[str] = []

    def _patch(match: re.Match[str]) -> str:
        raw = match.group(1)
        obj, trailing, err = parse_chart_fence_body(raw)
        if err or not obj or obj.get("view") != "WeekView":
            return match.group(0)
        params = dict(obj.get("params") or {})
        raw_ids = params.get("student_ids")
        needs_patch = False
        if not isinstance(raw_ids, list):
            needs_patch = True
        else:
            clean = clean_student_ids([str(x) for x in raw_ids])
            if not clean or any(is_placeholder_student_id(str(x)) for x in raw_ids):
                needs_patch = True
        if not needs_patch:
            return match.group(0)
        params["student_ids"] = canon_ids
        if canon_wr is not None:
            params["week_range"] = canon_wr
        obj["params"] = params
        notes.append("patched WeekView report-chart student_ids from build_visual_links")
        formatted = json.dumps(obj, ensure_ascii=False, indent=2)
        suffix = f"\n\n{trailing}" if trailing else ""
        return f"```report-chart\n{formatted}\n```{suffix}"

    text = _CHART_FENCE_RE.sub(_patch, source or "")
    return text, notes


def dedupe_report_chart_fences(
    source: str,
    *,
    protocol_path: Path | None = None,
) -> tuple[str, list[str]]:
    """Remove extra report-chart blocks beyond max_per_view (keep richest params)."""
    protocol = load_chart_protocol(protocol_path)
    limits = protocol.get("limits") or {}
    max_per_view: dict[str, int] = dict(limits.get("max_per_view") or {})
    if not max_per_view:
        return source, []

    matches = list(_CHART_FENCE_RE.finditer(source or ""))
    if not matches:
        return source, []

    ranked: list[tuple[int, int, str, dict[str, Any], int]] = []
    for order, match in enumerate(matches):
        obj, trailing, err = parse_chart_fence_body(match.group(1))
        if err or trailing or not obj:
            ranked.append((order, -1, "?", {}, -1))
            continue
        view = str(obj.get("view") or obj.get("panel") or "?")
        params = obj.get("params") if isinstance(obj.get("params"), dict) else {}
        ranked.append(
            (order, match.start(), view, params, _chart_block_score(view, params))
        )

    keep_orders: set[int] = set()
    by_view: dict[str, list[tuple[int, int]]] = {}
    for order, _start, view, _params, score in ranked:
        if score < 0:
            keep_orders.add(order)
            continue
        if view not in max_per_view:
            keep_orders.add(order)
            continue
        by_view.setdefault(view, []).append((order, score))

    notes: list[str] = []
    for view, cap in max_per_view.items():
        entries = by_view.get(view) or []
        if len(entries) <= cap:
            for order, _ in entries:
                keep_orders.add(order)
            continue
        entries.sort(key=lambda item: (-item[1], item[0]))
        for order, _ in entries[:cap]:
            keep_orders.add(order)
        removed = len(entries) - cap
        if removed > 0:
            notes.append(f"removed {removed} duplicate {view} report-chart block(s)")

    if len(keep_orders) == len(matches):
        return source, notes

    parts: list[str] = []
    last = 0
    for order, match in enumerate(matches):
        if order in keep_orders:
            parts.append(source[last : match.end()])
        else:
            parts.append(source[last : match.start()])
        last = match.end()
    parts.append(source[last:])
    return "".join(parts), notes

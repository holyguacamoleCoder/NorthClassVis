from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from common.paths import PROJECT_ROOT

_META_DIR = PROJECT_ROOT / "data" / "meta"
_DEFAULT_RULES_PATH = _META_DIR / "report_quality_rules.yaml"

_SECTION_RE = re.compile(r"^(#{2,4})\s+(.+?)\s*$", re.MULTILINE)
_TABLE_ROW_RE = re.compile(r"^\s*\|.+\|\s*$")
_TABLE_SEP_RE = re.compile(r"^\s*\|[\s:\-|]+\|\s*$")
_NUMBERING_PREFIX_RE = re.compile(r"^[\d]+[\.\)、:\s]+")
_CHINESE_ENUM_PREFIX_RE = re.compile(r"^[一二三四五六七八九十]+[、．.\s]+")


@lru_cache(maxsize=1)
def _load_rules_cached(path_str: str) -> dict[str, Any]:
    with Path(path_str).open(encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def load_quality_rules(rules_path: Path | None = None) -> dict[str, Any]:
    path = rules_path or _DEFAULT_RULES_PATH
    return _load_rules_cached(str(path.resolve()))


@dataclass
class ReportSection:
    id: str
    title: str
    body: str
    line_count: int
    table_rows: int


@dataclass
class ParsedReport:
    preamble: str
    sections: list[ReportSection] = field(default_factory=list)
    total_lines: int = 0

    def section_map(self) -> dict[str, ReportSection]:
        return {s.id: s for s in self.sections}


def _normalize_section_id(raw: str) -> str:
    text = raw.strip().lower()
    text = _CHINESE_ENUM_PREFIX_RE.sub("", text)
    text = _NUMBERING_PREFIX_RE.sub("", text)
    text = re.sub(r"\s+", "_", text)
    return text


def _build_alias_lookup(aliases: dict[str, Any] | None) -> dict[str, str]:
    lookup: dict[str, str] = {}
    if not aliases:
        return lookup
    for canonical, variants in aliases.items():
        canon = str(canonical).strip()
        lookup[_normalize_section_id(canon)] = canon
        if not isinstance(variants, list):
            continue
        for variant in variants:
            lookup[_normalize_section_id(str(variant))] = canon
    return lookup


def resolve_section_id(
    raw_title: str,
    *,
    aliases: dict[str, Any] | None = None,
) -> str:
    """Normalize heading text and map Chinese/numbered titles to ontology ids."""
    lookup = _build_alias_lookup(aliases)
    norm = _normalize_section_id(raw_title)
    return lookup.get(norm, norm)


def normalize_section_id(raw: str) -> str:
    """Public normalize for section heading matching (no alias map)."""
    return _normalize_section_id(raw)


def load_section_aliases(rules_path: Path | None = None) -> dict[str, Any]:
    global_rules = load_quality_rules(rules_path).get("global") or {}
    raw = global_rules.get("section_id_aliases") or {}
    return raw if isinstance(raw, dict) else {}


def load_canonical_section_ids(rules_path: Path | None = None) -> set[str]:
    """Ontology section ids used for coverage and heading recognition."""
    rules = load_quality_rules(rules_path)
    ids: set[str] = set(load_section_aliases(rules_path).keys())
    for tier_rules in (rules.get("tiers") or {}).values():
        if isinstance(tier_rules, dict):
            ids.update(str(s) for s in (tier_rules.get("required_sections") or []))
    tail = (rules.get("global") or {}).get("required_tail_sections") or []
    ids.update(str(s) for s in tail)
    return ids


def load_validation_level_config(
    level: str,
    *,
    rules_path: Path | None = None,
) -> dict[str, Any]:
    rules = load_quality_rules(rules_path)
    levels = (rules.get("global") or {}).get("validation_levels") or {}
    cfg = levels.get(level) or levels.get("deliver") or {}
    return cfg if isinstance(cfg, dict) else {}


def _count_body_lines(body: str) -> int:
    return sum(1 for line in body.splitlines() if line.strip())


def _count_table_rows(body: str) -> int:
    count = 0
    for line in body.splitlines():
        if not _TABLE_ROW_RE.match(line):
            continue
        if _TABLE_SEP_RE.match(line):
            continue
        count += 1
    return count


def parse_report_markdown(
    source: str,
    *,
    rules_path: Path | None = None,
) -> ParsedReport:
    text = source or ""
    total_lines = sum(1 for line in text.splitlines() if line.strip())
    matches = list(_SECTION_RE.finditer(text))
    if not matches:
        return ParsedReport(preamble=text.strip(), total_lines=total_lines)

    aliases = load_section_aliases(rules_path)
    canonical_ids = load_canonical_section_ids(rules_path)
    preamble = text[: matches[0].start()].strip() if matches else text.strip()

    # Preamble ends before the first recognized ontology section.
    first_section_idx = 0
    for idx, match in enumerate(matches):
        title = match.group(2).strip()
        sid = resolve_section_id(title, aliases=aliases)
        if sid in canonical_ids:
            first_section_idx = idx
            preamble = text[: match.start()].strip()
            break
    else:
        return ParsedReport(preamble=preamble, total_lines=total_lines)

    sections: list[ReportSection] = []
    seen_ids: set[str] = set()
    for idx in range(first_section_idx, len(matches)):
        match = matches[idx]
        title = match.group(2).strip()
        sid = resolve_section_id(title, aliases=aliases)
        if sid not in canonical_ids:
            continue
        if sid in seen_ids:
            continue
        seen_ids.add(sid)
        start = match.end()
        end = len(text)
        for later in range(idx + 1, len(matches)):
            later_title = matches[later].group(2).strip()
            later_sid = resolve_section_id(later_title, aliases=aliases)
            if later_sid in canonical_ids:
                end = matches[later].start()
                break
        body = text[start:end].strip()
        sections.append(
            ReportSection(
                id=sid,
                title=title,
                body=body,
                line_count=_count_body_lines(body),
                table_rows=_count_table_rows(body),
            )
        )
    return ParsedReport(preamble=preamble, sections=sections, total_lines=total_lines)


def infer_tier_from_path(path: str | Path) -> str:
    raw = str(path).replace("\\", "/").lower()
    if "/student/" in raw or raw.startswith("reports/student/"):
        return "student"
    if "/class/" in raw or raw.startswith("reports/class/"):
        return "class"
    if "/major/" in raw or raw.startswith("reports/major/"):
        return "major"
    if "/notes/" in raw or raw.startswith("reports/notes/"):
        return "freeform"
    return "freeform"

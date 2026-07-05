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


@lru_cache(maxsize=1)
def _load_rules_cached(path_str: str) -> dict[str, Any]:
    with Path(path_str).open(encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def load_quality_rules(rules_path: Path | None = None) -> dict[str, Any]:
    path = rules_path or _DEFAULT_RULES_PATH
    return _load_rules_cached(str(path.resolve()))


_SECTION_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
_TABLE_ROW_RE = re.compile(r"^\s*\|.+\|\s*$")
_TABLE_SEP_RE = re.compile(r"^\s*\|[\s:\-|]+\|\s*$")


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
    text = re.sub(r"\s+", "_", text)
    return text


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


def parse_report_markdown(source: str) -> ParsedReport:
    text = source or ""
    total_lines = sum(1 for line in text.splitlines() if line.strip())
    matches = list(_SECTION_RE.finditer(text))
    if not matches:
        return ParsedReport(preamble=text.strip(), total_lines=total_lines)

    preamble = text[: matches[0].start()].strip()
    sections: list[ReportSection] = []
    for idx, match in enumerate(matches):
        title = match.group(1).strip()
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        sections.append(
            ReportSection(
                id=_normalize_section_id(title),
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

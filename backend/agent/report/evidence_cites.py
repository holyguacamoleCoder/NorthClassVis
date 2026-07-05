from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from common.paths import PROJECT_ROOT

_META_DIR = PROJECT_ROOT / "data" / "meta"
_DEFAULT_PROTOCOL_PATH = _META_DIR / "evidence_cite_protocol.yaml"


@lru_cache(maxsize=1)
def _load_protocol_cached(path_str: str) -> dict[str, Any]:
    with Path(path_str).open(encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def load_cite_protocol(protocol_path: Path | None = None) -> dict[str, Any]:
    path = protocol_path or _DEFAULT_PROTOCOL_PATH
    return _load_protocol_cached(str(path.resolve()))


@dataclass
class EvidenceCite:
    kind: str
    target: str
    summary: str | None
    raw: str


@dataclass
class CiteValidation:
    cites: list[EvidenceCite] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def extract_evidence_cites(
    source: str,
    *,
    protocol_path: Path | None = None,
) -> list[EvidenceCite]:
    protocol = load_cite_protocol(protocol_path)
    pattern = protocol.get("cite_pattern") or r"\[@(ds|ref):([^\s\]]+)(?:\s+([^\]]+))?\]"
    regex = re.compile(pattern)
    cites: list[EvidenceCite] = []
    for match in regex.finditer(source or ""):
        kind = match.group(1)
        target = match.group(2).strip()
        summary = match.group(3).strip() if match.lastindex and match.group(3) else None
        cites.append(
            EvidenceCite(
                kind=kind,
                target=target,
                summary=summary,
                raw=match.group(0),
            )
        )
    return cites


def validate_evidence_section(
    evidence_body: str,
    *,
    protocol_path: Path | None = None,
    require_at_least_one_cite: bool = False,
) -> CiteValidation:
    result = CiteValidation()
    result.cites = extract_evidence_cites(evidence_body, protocol_path=protocol_path)

    if require_at_least_one_cite and not result.cites:
        stripped = (evidence_body or "").strip()
        if stripped:
            result.warnings.append(
                "Evidence section has text but no [@ds:…] or [@ref:…] cite tags"
            )
        else:
            result.warnings.append("Evidence section is empty")

    for cite in result.cites:
        if cite.kind == "ref" and not cite.target.startswith("query-results/"):
            result.warnings.append(
                f"ref cite should use query-results/ prefix: {cite.target!r}"
            )

    return result

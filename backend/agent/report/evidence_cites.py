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

_RESULT_REF_TOKEN = re.compile(r"^[0-9a-f]{32}(?:\.json)?$", re.I)
_RESULT_REF_PATH = re.compile(r"^query-results/[0-9a-f]{32}\.json$", re.I)


def normalize_result_ref(target: str) -> str:
    """Normalize cite target or bare UUID to query-results/<id>.json."""
    raw = str(target or "").strip().replace("\\", "/")
    if raw.startswith("query-results/"):
        return raw if raw.endswith(".json") else f"{raw}.json"
    base = raw.split("/")[-1]
    if not base.endswith(".json"):
        base = f"{base}.json"
    return f"query-results/{base}"


def is_result_ref_token(target: str) -> bool:
    raw = str(target or "").strip().replace("\\", "/")
    if _RESULT_REF_TOKEN.match(raw):
        return True
    if raw.startswith("query-results/"):
        norm = raw if raw.endswith(".json") else f"{raw}.json"
        return bool(_RESULT_REF_PATH.match(norm))
    return False


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
    legacy_link: bool = False


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


def extract_evidence_links(
    source: str,
    *,
    protocol_path: Path | None = None,
) -> list[EvidenceCite]:
    """Legacy markdown links to query-results/ (discouraged; migrate to [@ref:…])."""
    protocol = load_cite_protocol(protocol_path)
    pattern = (
        protocol.get("legacy_link_pattern")
        or r"\[[^\]]+\]\((query-results/[^)\s]+)\)"
    )
    regex = re.compile(pattern, re.IGNORECASE)
    cites: list[EvidenceCite] = []
    for match in regex.finditer(source or ""):
        target = match.group(1).strip().replace("\\", "/")
        cites.append(
            EvidenceCite(
                kind="ref",
                target=target,
                summary=None,
                raw=match.group(0),
                legacy_link=True,
            )
        )
    return cites


def collect_evidence_sources(
    source: str,
    *,
    protocol_path: Path | None = None,
) -> list[EvidenceCite]:
    """Cite tags plus legacy markdown links (deduped by kind+target)."""
    cites = extract_evidence_cites(source, protocol_path=protocol_path)
    seen = {(c.kind, c.target) for c in cites}
    for link in extract_evidence_links(source, protocol_path=protocol_path):
        key = (link.kind, link.target)
        if key not in seen:
            cites.append(link)
            seen.add(key)
    return cites


def validate_evidence_section(
    evidence_body: str,
    *,
    protocol_path: Path | None = None,
    require_at_least_one_cite: bool = False,
) -> CiteValidation:
    result = CiteValidation()
    tag_cites = extract_evidence_cites(evidence_body, protocol_path=protocol_path)
    legacy_links = extract_evidence_links(evidence_body, protocol_path=protocol_path)
    result.cites = collect_evidence_sources(evidence_body, protocol_path=protocol_path)

    for link in legacy_links:
        result.errors.append(
            "Evidence uses markdown link; replace with [@ref:"
            f"{link.target}] cite tag (found {link.raw!r})"
        )

    if require_at_least_one_cite and not tag_cites:
        stripped = (evidence_body or "").strip()
        if stripped:
            result.errors.append(
                "Evidence section has text but no [@ds:…] or [@ref:…] cite tags"
            )
        else:
            result.errors.append("Evidence section is empty")

    for cite in tag_cites:
        if cite.kind == "ref" and not cite.target.startswith("query-results/"):
            result.warnings.append(
                f"ref cite should use query-results/ prefix: {cite.target!r}"
            )
        if cite.kind == "ds" and is_result_ref_token(cite.target):
            ref = normalize_result_ref(cite.target)
            result.warnings.append(
                f"[@ds:{cite.target}] 实为 result_ref；聚合输出请用 [@ref:{ref}]，"
                "query 数据集请用 list_datasets 返回的 ds_… id"
            )

    return result

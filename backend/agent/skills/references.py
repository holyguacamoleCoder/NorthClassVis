from __future__ import annotations

import os
from pathlib import Path

from .registry import BASE_DIR


def skills_dir() -> Path:
    env_dir = os.environ.get("AGENT_SKILLS_DIR", "").strip()
    if env_dir:
        return Path(env_dir)
    return BASE_DIR / "skills"


def resolve_reference_path(name: str) -> Path | None:
    raw = (name or "").strip().replace("\\", "/")
    normalized = "/".join(p for p in raw.split("/") if p and p != ".")
    if not normalized:
        return None
    root = skills_dir()
    candidates = [
        root / normalized,
        root / "report-writing" / "references" / normalized,
        root / "report-writing" / "references" / f"{normalized}.md",
    ]
    for path in candidates:
        if path.is_file():
            return path
    return None


def read_reference_text(name: str) -> tuple[str, str] | None:
    path = resolve_reference_path(name)
    if path is None:
        return None
    try:
        rel = path.relative_to(skills_dir()).as_posix()
    except Exception:
        rel = path.as_posix()
    text = path.read_text(encoding="utf-8").strip()
    return rel, text

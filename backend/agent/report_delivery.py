"""Serve agent-written deliverables under data/reports/ and data/exports/."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from common.paths import DATA_DIR

from .permission.paths import (
    WRITABLE_SUBDIRS,
    normalize_path,
    resolve_data_relative_path,
)

_WRITE_OK_RE = re.compile(
    r"\[(?:Write|Edit)\s+OK:\s*path=([^,\]]+)",
    re.IGNORECASE,
)


def parse_deliverable_path_from_tool_content(content: str) -> str | None:
    match = _WRITE_OK_RE.search(content or "")
    if not match:
        return None
    return match.group(1).strip()


def deliverable_label(rel_path: str) -> str:
    stem = Path(rel_path).stem
    if not stem:
        return rel_path
    return stem.replace("_", " ").replace("-", " ")


def _resolve_readable_file(rel_path: str) -> Path:
    normalized = resolve_data_relative_path(rel_path)
    parts = normalized.split("/")
    if not parts or parts[0] not in WRITABLE_SUBDIRS:
        raise ValueError("仅允许访问 reports/ 或 exports/ 下的文件")
    full = (DATA_DIR / normalized).resolve()
    try:
        full.relative_to(DATA_DIR.resolve())
    except ValueError as exc:
        raise ValueError("路径超出 data 目录") from exc
    if not full.is_file():
        raise FileNotFoundError(normalized)
    return full


def read_deliverable(rel_path: str) -> dict[str, Any]:
    full = _resolve_readable_file(rel_path)
    rel = full.relative_to(DATA_DIR.resolve()).as_posix()
    stat = full.stat()
    suffix = full.suffix.lower()
    if suffix in (".md", ".txt", ".json", ".csv", ".yaml", ".yml"):
        text = full.read_text(encoding="utf-8", errors="replace")
    else:
        text = ""
    return {
        "path": rel,
        "title": deliverable_label(rel),
        "filename": full.name,
        "content": text,
        "bytes": stat.st_size,
        "updated_at": stat.st_mtime,
        "mime": _guess_mime(suffix),
    }


def deliverable_disk_path(rel_path: str) -> Path:
    return _resolve_readable_file(rel_path)


def report_link_from_tool(
    tool_name: str,
    content: str,
    params: dict[str, Any] | None = None,
) -> dict[str, str] | None:
    if tool_name not in ("write_file", "edit_file"):
        return None
    if not (content or "").strip().startswith("["):
        if "OK" not in (content or ""):
            return None
    rel = parse_deliverable_path_from_tool_content(content)
    if not rel:
        arg_path = (params or {}).get("path")
        if arg_path:
            rel = str(arg_path).strip()
    if not rel:
        return None
    if (content or "").strip().startswith("Error"):
        return None
    try:
        resolve_data_relative_path(rel)
        rel_norm = normalize_path(rel)
        parts = rel_norm.split("/")
        if not parts or parts[0] not in WRITABLE_SUBDIRS:
            return None
    except ValueError:
        return None
    return {
        "path": rel_norm,
        "label": deliverable_label(rel_norm),
    }


def _guess_mime(suffix: str) -> str:
    return {
        ".md": "text/markdown",
        ".txt": "text/plain",
        ".json": "application/json",
        ".csv": "text/csv",
    }.get(suffix, "application/octet-stream")

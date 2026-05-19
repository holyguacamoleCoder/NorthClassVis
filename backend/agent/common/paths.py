"""Shared path constants: data plane (tool sandbox) vs agent state (governance)."""

from __future__ import annotations

import json
import logging
import os
import shutil
from pathlib import Path
from typing import Any

from common.logger import get_logger, log_event

_log = get_logger("paths")

PROJECT_ROOT = Path(__file__).resolve().parents[3]  # NorthClassVision
BACKEND_DIR = Path(__file__).resolve().parents[2]  # backend/

# Business data + teacher deliverables (agent tools sandbox).
DATA_DIR = PROJECT_ROOT / "data"

# Agent runtime / governance (under backend/, not repo root or data/).
AGENT_STATE_DIR = Path(
    os.environ.get("AGENT_STATE_DIR", str(BACKEND_DIR / ".agent"))
).resolve()

SESSIONS_DIR = AGENT_STATE_DIR / "sessions"
TRANSCRIPTS_DIR = AGENT_STATE_DIR / "transcripts"
TOOL_RESULTS_DIR = AGENT_STATE_DIR / "task_outputs" / "tool-results"
AUDIT_DIR = AGENT_STATE_DIR / "audit"
MEMORY_DIR = AGENT_STATE_DIR / "memory"

# Legacy locations (pre-migration).
LEGACY_MEMORY_DIRS = (
    PROJECT_ROOT / ".memory",
    PROJECT_ROOT / "backend" / "agent" / ".memory",
)
LEGACY_RELOCATIONS: tuple[tuple[Path, Path], ...] = (
    (PROJECT_ROOT / ".agent", AGENT_STATE_DIR),
    (DATA_DIR / ".sessions", SESSIONS_DIR),
    (DATA_DIR / ".transcripts", TRANSCRIPTS_DIR),
    (DATA_DIR / ".task_outputs", AGENT_STATE_DIR / "task_outputs"),
    (DATA_DIR / ".agent_audit", AUDIT_DIR),
    *((src, MEMORY_DIR) for src in LEGACY_MEMORY_DIRS),
)

# Tool paths under data/ that must never be read/written (old layout).
DATA_GOVERNANCE_DENY_PATTERNS: tuple[str, ...] = (
    ".sessions/**",
    ".transcripts/**",
    ".task_outputs/**",
    ".agent_audit/**",
    "**/.sessions/**",
    "**/.transcripts/**",
    "**/.task_outputs/**",
    "**/.agent_audit/**",
)

_bootstrapped = False


def strip_data_prefix(path: str) -> str:
    """
    Normalize a tool path segment relative to data/ without destroying dot-prefixed names.

    Strips optional leading ./ and data/ only — never uses lstrip(\"./\") which would
    turn \".sessions/foo\" into \"sessions/foo\".
    """
    raw = str(path or "").strip().replace("\\", "/")
    while raw.startswith("./"):
        raw = raw[2:]
    if raw.startswith("data/"):
        raw = raw[5:]
    return raw


def _dir_has_entries(path: Path) -> bool:
    if not path.is_dir():
        return False
    try:
        return any(path.iterdir())
    except OSError:
        return False


def _relocate_tree(src: Path, dst: Path) -> bool:
    """Move src → dst, or merge children if dst already has content."""
    if not src.exists():
        return False
    if not _dir_has_entries(src) and src.is_dir():
        try:
            src.rmdir()
        except OSError:
            pass
        return False

    dst.parent.mkdir(parents=True, exist_ok=True)
    if not dst.exists():
        shutil.move(str(src), str(dst))
        log_event(_log, logging.INFO, "agent_state_relocated", src=str(src), dst=str(dst))
        return True

    if dst.is_dir() and not _dir_has_entries(dst):
        try:
            dst.rmdir()
        except OSError:
            pass
        shutil.move(str(src), str(dst))
        log_event(_log, logging.INFO, "agent_state_relocated", src=str(src), dst=str(dst))
        return True

    if not src.is_dir() or not dst.is_dir():
        return False

    moved = False
    for child in list(src.iterdir()):
        target = dst / child.name
        if target.exists():
            if child.is_dir() and target.is_dir():
                if _relocate_tree(child, target):
                    moved = True
            continue
        shutil.move(str(child), str(target))
        moved = True
    if moved:
        log_event(
            _log,
            logging.INFO,
            "agent_state_merged",
            src=str(src),
            dst=str(dst),
        )
    if src.is_dir() and not _dir_has_entries(src):
        try:
            src.rmdir()
        except OSError:
            pass
    return moved


def _load_session_index(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    return [x for x in data if isinstance(x, dict)] if isinstance(data, list) else []


def _merge_sessions_index(legacy_dir: Path, target_dir: Path) -> bool:
    """Union session index entries; prefer newer updated_at per id."""
    legacy_index = legacy_dir / "index.json"
    target_index = target_dir / "index.json"
    legacy_rows = _load_session_index(legacy_index)
    if not legacy_rows:
        return False
    merged: dict[str, dict[str, Any]] = {
        str(row["id"]): row for row in _load_session_index(target_index) if row.get("id")
    }
    for row in legacy_rows:
        sid = str(row.get("id") or "")
        if not sid:
            continue
        prev = merged.get(sid)
        if prev is None or float(row.get("updated_at") or 0) >= float(prev.get("updated_at") or 0):
            merged[sid] = row
    target_dir.mkdir(parents=True, exist_ok=True)
    payload = sorted(merged.values(), key=lambda r: float(r.get("updated_at") or 0), reverse=True)
    target_index.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    legacy_active = legacy_dir / "active.json"
    target_active = target_dir / "active.json"
    if legacy_active.is_file():
        try:
            legacy_id = json.loads(legacy_active.read_text(encoding="utf-8")).get("session_id")
            if legacy_id and legacy_id in merged:
                target_active.write_text(
                    json.dumps({"session_id": legacy_id}, ensure_ascii=False),
                    encoding="utf-8",
                )
        except (json.JSONDecodeError, OSError, TypeError):
            pass
    return True


def migrate_legacy_agent_state() -> list[str]:
    """Move governance dirs from repo root / data/ / legacy .memory into backend/.agent/."""
    completed: list[str] = []
    for src, dst in LEGACY_RELOCATIONS:
        if _relocate_tree(src, dst):
            completed.append(f"{src.name} → {dst}")

    legacy_root_agent = PROJECT_ROOT / ".agent"
    if legacy_root_agent.is_dir():
        _merge_sessions_index(legacy_root_agent / "sessions", SESSIONS_DIR)
        if _dir_has_entries(legacy_root_agent / "sessions"):
            _relocate_tree(legacy_root_agent / "sessions", SESSIONS_DIR)
        if not _dir_has_entries(legacy_root_agent):
            try:
                legacy_root_agent.rmdir()
            except OSError:
                pass
        elif _dir_has_entries(legacy_root_agent / "sessions") and not any(
            (legacy_root_agent / "sessions").iterdir()
        ):
            try:
                (legacy_root_agent / "sessions").rmdir()
                if not _dir_has_entries(legacy_root_agent):
                    legacy_root_agent.rmdir()
            except OSError:
                pass

    return completed


def ensure_agent_state_dirs() -> None:
    for path in (
        AGENT_STATE_DIR,
        SESSIONS_DIR,
        TRANSCRIPTS_DIR,
        TOOL_RESULTS_DIR,
        AUDIT_DIR,
        MEMORY_DIR,
    ):
        path.mkdir(parents=True, exist_ok=True)


def bootstrap_agent_paths(*, migrate: bool = True) -> None:
    """Idempotent: migrate legacy paths then ensure backend/.agent layout."""
    global _bootstrapped
    if _bootstrapped:
        return
    if migrate:
        migrate_legacy_agent_state()
    ensure_agent_state_dirs()
    _bootstrapped = True


def agent_state_display_path(path: Path) -> str:
    """Human-readable path for logs / tool previews (relative to project when possible)."""
    try:
        return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()

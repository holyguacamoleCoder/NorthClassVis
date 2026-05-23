"""Shared helpers for NorthClassVision agent hook scripts."""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"


def _env_path(name: str, default: Path) -> Path:
    raw = os.environ.get(name, "").strip()
    return Path(raw) if raw else default


AGENT_STATE_DIR = Path(
    os.environ.get("AGENT_STATE_DIR", str(ROOT / "backend" / ".agent"))
).resolve()
AUDIT_DIR = _env_path("AGENT_AUDIT_DIR", AGENT_STATE_DIR / "audit")
READ_AUDIT_LOG = _env_path("AGENT_READ_AUDIT_LOG", AUDIT_DIR / "read.jsonl")

# Migrate legacy audit dir on hook import (hooks run in separate processes).
_LEGACY_AUDIT = DATA_DIR / ".agent_audit"
if _LEGACY_AUDIT.is_dir() and _LEGACY_AUDIT != AUDIT_DIR and not (AUDIT_DIR / "read.jsonl").exists():
    try:
        import shutil

        AUDIT_DIR.parent.mkdir(parents=True, exist_ok=True)
        if not AUDIT_DIR.exists():
            shutil.move(str(_LEGACY_AUDIT), str(AUDIT_DIR))
        elif not any(AUDIT_DIR.iterdir()):
            shutil.rmtree(AUDIT_DIR, ignore_errors=True)
            shutil.move(str(_LEGACY_AUDIT), str(AUDIT_DIR))
    except OSError:
        pass
EXPORT_MANIFEST = _env_path(
    "AGENT_EXPORT_MANIFEST", DATA_DIR / "exports" / "manifest.jsonl"
)
DATA_CATALOG = _env_path(
    "AGENT_DATA_CATALOG", DATA_DIR / "meta" / "data_catalog.md"
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def hook_event() -> str:
    return os.environ.get("HOOK_EVENT", "")


def hook_tool_name() -> str:
    return os.environ.get("HOOK_TOOL_NAME", "")


def hook_tool_input() -> dict:
    raw = os.environ.get("HOOK_TOOL_INPUT", "{}")
    try:
        data = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def hook_deny_reason() -> str:
    return os.environ.get("HOOK_DENY_REASON", "").strip()


def hook_permission_mode() -> str:
    return os.environ.get("HOOK_PERMISSION_MODE", "").strip().lower()


def hook_deny_type() -> str:
    return os.environ.get("HOOK_DENY_TYPE", "").strip().lower()


def is_deliverable_path(path: str) -> bool:
    norm = normalize_data_path(path)
    return norm.startswith("reports/") or norm.startswith("exports/")


def normalize_data_path(path: str) -> str:
    raw = str(path or "").strip().replace("\\", "/")
    while raw.startswith("./"):
        raw = raw[2:]
    if raw.startswith("data/"):
        raw = raw[5:]
    return raw


def is_sensitive_source(path: str) -> bool:
    """Raw datasets and submit-record trees (audit-worthy reads)."""
    norm = normalize_data_path(path)
    if not norm:
        return False
    lower = norm.lower()
    if lower.startswith("data_submitrecord/"):
        return True
    name = Path(norm).name
    if name.startswith("Data_") and name.endswith(".csv"):
        return True
    return False


def write_json_stdout(payload: dict) -> None:
    """Emit hook JSON on stdout as UTF-8 (Windows default console encoding may be GBK)."""
    sys.stdout.buffer.write(json.dumps(payload, ensure_ascii=False).encode("utf-8"))


def append_jsonl(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, ensure_ascii=False, default=str)
    with path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")

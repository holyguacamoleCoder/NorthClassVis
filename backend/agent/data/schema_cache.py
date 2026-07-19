"""Session-scoped cache for inspect_schema payloads (avoid reloading DataFrames)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from common.paths import AGENT_STATE_DIR

CACHE_FILE = "schema_cache.json"
MAX_ENTRIES = 32


def _cache_path(session_id: str) -> Path:
    return AGENT_STATE_DIR / "sessions" / session_id / CACHE_FILE


def cache_key(resource: str, resolve_params: dict[str, Any] | None = None) -> str:
    payload = {
        "resource": str(resource or "").strip(),
        "resolve": _normalize_params(resolve_params or {}),
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def _normalize_params(params: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key in sorted(params.keys()):
        val = params[key]
        if val is None or val == "" or val == [] or val == {}:
            continue
        if isinstance(val, (list, tuple)):
            out[key] = [str(x) for x in val]
        else:
            out[key] = val
    return out


def get_cached_schema(
    session_id: str | None,
    resource: str,
    resolve_params: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    if not session_id:
        return None
    path = _cache_path(session_id)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(data, dict):
        return None
    entries = data.get("entries") or {}
    if not isinstance(entries, dict):
        return None
    key = cache_key(resource, resolve_params)
    hit = entries.get(key)
    return dict(hit) if isinstance(hit, dict) else None


def put_cached_schema(
    session_id: str | None,
    resource: str,
    payload: dict[str, Any],
    resolve_params: dict[str, Any] | None = None,
) -> None:
    if not session_id or not isinstance(payload, dict):
        return
    path = _cache_path(session_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    entries: dict[str, Any] = {}
    if path.is_file():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(raw, dict) and isinstance(raw.get("entries"), dict):
                entries = dict(raw["entries"])
        except (json.JSONDecodeError, OSError):
            entries = {}
    key = cache_key(resource, resolve_params)
    # Store a slightly slimmed copy: keep columns + hints, trim huge samples.
    stored = dict(payload)
    sample = stored.get("sample_rows")
    if isinstance(sample, list) and len(sample) > 5:
        stored["sample_rows"] = sample[:5]
    entries.pop(key, None)
    entries[key] = stored
    while len(entries) > MAX_ENTRIES:
        oldest = next(iter(entries))
        entries.pop(oldest, None)
    path.write_text(
        json.dumps({"entries": entries}, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )

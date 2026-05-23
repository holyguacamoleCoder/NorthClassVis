from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from common.paths import AGENT_STATE_DIR

QUERY_RESULTS_DIR = AGENT_STATE_DIR / "task_outputs" / "query-results"


def _ensure_dir() -> Path:
    QUERY_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    return QUERY_RESULTS_DIR


def save_result(payload: dict[str, Any], *, ref_id: str | None = None) -> str:
    """持久化 TabularResult，返回 result_ref（相对 query-results/ 的文件名）。"""
    _ensure_dir()
    name = ref_id or f"{uuid.uuid4().hex}.json"
    if not name.endswith(".json"):
        name = f"{name}.json"
    path = QUERY_RESULTS_DIR / name
    path.write_text(json.dumps(payload, ensure_ascii=False, default=str), encoding="utf-8")
    return f"query-results/{name}"


def load_result(result_ref: str) -> dict[str, Any]:
    """按 result_ref 加载 TabularResult。"""
    ref = result_ref.strip().replace("\\", "/")
    if ref.startswith("query-results/"):
        ref = ref[len("query-results/") :]
    path = QUERY_RESULTS_DIR / ref
    if not path.is_file():
        raise FileNotFoundError(f"result_ref 不存在: {result_ref!r}")
    return json.loads(path.read_text(encoding="utf-8"))

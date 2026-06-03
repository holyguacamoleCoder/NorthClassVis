"""Session-scoped deliverable index (reports/exports written this conversation)."""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from common.paths import AGENT_STATE_DIR

DELIVERABLES_FILE = "deliverables.jsonl"


@dataclass
class DeliverableRecord:
    path: str
    label: str
    kind: str  # report | export
    user_turn: int = 0
    note: str = ""
    created_at: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None and v != ""}


def _session_deliverables_path(session_id: str) -> Path:
    return AGENT_STATE_DIR / "sessions" / session_id / DELIVERABLES_FILE


def append_deliverable(session_id: str | None, record: DeliverableRecord) -> None:
    if not session_id or not record.path:
        return
    path = _session_deliverables_path(session_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = record.to_dict()
    if record.created_at is None:
        payload["created_at"] = time.time()
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")


def list_deliverables(session_id: str | None, *, tail: int = 20) -> list[DeliverableRecord]:
    if not session_id:
        return []
    path = _session_deliverables_path(session_id)
    if not path.is_file():
        return []
    rows: list[DeliverableRecord] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            raw = json.loads(line)
            rows.append(
                DeliverableRecord(
                    path=str(raw["path"]),
                    label=str(raw.get("label") or raw["path"]),
                    kind=str(raw.get("kind") or "report"),
                    user_turn=int(raw.get("user_turn", 0)),
                    note=str(raw.get("note") or ""),
                    created_at=raw.get("created_at"),
                )
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            continue
    return rows[-tail:]


def format_deliverables_prompt(session_id: str | None, *, tail: int = 5) -> str:
    rows = list_deliverables(session_id, tail=tail)
    if not rows:
        return ""
    lines = ["本会话已写入的交付物（仅当前对话，非跨会话记忆）:"]
    for rec in reversed(rows):
        suffix = f" — {rec.note}" if rec.note else ""
        lines.append(f"  - {rec.path} ({rec.label}){suffix}")
    return "\n".join(lines)


def record_deliverable_from_tool(
    session_id: str | None,
    *,
    rel_path: str,
    label: str,
    user_turn: int = 0,
) -> None:
    norm = rel_path.strip().replace("\\", "/")
    parts = norm.split("/")
    kind = parts[0] if parts else "report"
    if kind not in ("reports", "exports"):
        return
    append_deliverable(
        session_id,
        DeliverableRecord(
            path=norm,
            label=label or norm,
            kind="export" if kind == "exports" else "report",
            user_turn=user_turn,
        ),
    )

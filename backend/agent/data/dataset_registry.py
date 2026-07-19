"""Disk-side dataset catalog (session-scoped index over task_outputs files).

Memory vs disk:
- **Disk**: ``task_outputs/query-results/*.json`` — full TabularResult blobs (large, durable).
- **Catalog**: ``.agent/sessions/<id>/datasets.jsonl`` — append-only registry (id, ref, metadata).
- **Working set** (see ``loop_state.AnalysisToolContext``): ``working_active_ref`` — last query
  in the *current user turn* only; not used across teacher questions.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from common.paths import AGENT_STATE_DIR


@dataclass
class DatasetRecord:
    dataset_id: str
    result_ref: str
    user_turn: int
    resource: str | None = None
    result_rows: int = 0
    query_limit: int | None = None
    rows_scanned: int | None = None
    classes: list[str] | None = None
    created_at: float | None = None
    query_fingerprint: str | None = None
    query_core_fingerprint: str | None = None
    select_cols: list[str] | None = None
    grain: str | None = None  # row | agg
    label: str | None = None
    columns: list[str] | None = None
    dimensions: list[str] | None = None
    # Aggregate lineage: upstream row/slice dataset this agg was built from.
    parent_dataset_id: str | None = None
    source_result_ref: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


def _session_datasets_path(session_id: str) -> Path:
    return AGENT_STATE_DIR / "sessions" / session_id / "datasets.jsonl"


def append_dataset(session_id: str | None, record: DatasetRecord) -> None:
    if not session_id:
        return
    path = _session_datasets_path(session_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record.to_dict(), ensure_ascii=False, default=str) + "\n")


def list_datasets(session_id: str | None, *, tail: int = 20) -> list[DatasetRecord]:
    if not session_id:
        return []
    path = _session_datasets_path(session_id)
    if not path.is_file():
        return []
    rows: list[DatasetRecord] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            raw = json.loads(line)
            rows.append(
                DatasetRecord(
                    dataset_id=str(raw["dataset_id"]),
                    result_ref=str(raw["result_ref"]),
                    user_turn=int(raw.get("user_turn", 0)),
                    resource=raw.get("resource"),
                    result_rows=int(raw.get("result_rows", 0)),
                    query_limit=raw.get("query_limit"),
                    rows_scanned=raw.get("rows_scanned"),
                    classes=raw.get("classes"),
                    created_at=raw.get("created_at"),
                    query_fingerprint=raw.get("query_fingerprint"),
                    query_core_fingerprint=raw.get("query_core_fingerprint"),
                    select_cols=raw.get("select_cols"),
                    grain=raw.get("grain"),
                    label=raw.get("label"),
                    columns=raw.get("columns"),
                    dimensions=raw.get("dimensions"),
                    parent_dataset_id=raw.get("parent_dataset_id"),
                    source_result_ref=raw.get("source_result_ref"),
                )
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            continue
    return rows[-tail:]


def resolve_dataset_id(session_id: str | None, dataset_id: str) -> str | None:
    rec = get_dataset_record(session_id, dataset_id)
    return rec.result_ref if rec else None


def get_dataset_record(
    session_id: str | None,
    dataset_id: str,
) -> DatasetRecord | None:
    needle = dataset_id.strip()
    for rec in reversed(list_datasets(session_id, tail=200)):
        if rec.dataset_id == needle:
            return rec
    return None


def find_dataset_by_ref(
    session_id: str | None,
    result_ref: str,
) -> DatasetRecord | None:
    norm = result_ref.strip().replace("\\", "/")
    for rec in reversed(list_datasets(session_id, tail=200)):
        if rec.result_ref.strip().replace("\\", "/") == norm:
            return rec
    return None


def format_catalog_hint(session_id: str | None, *, tail: int = 5) -> str:
    from data.dataset_identity import describe_for_catalog

    payload = build_datasets_catalog(session_id, tail=tail)
    rows = payload.get("datasets") or []
    if not rows:
        return ""
    lines = [
        "最近数据集（指代：看 grain/label；续算传 dataset_id；勿把「聚合表」当「原始行」）：",
    ]
    for item in rows:
        lines.append(f"  - {describe_for_catalog(item)}")
        ref = item.get("result_ref") or ""
        if ref:
            lines.append(f"      result_ref={ref}")
    lines.append(
        "按学生续算必须用 grain=row 且含 student_ID 的数据集；"
        "grain=agg 只能在其 dimensions 上再分析；"
        "agg 行若带 parent= 请优先用 parent 做学生级续算，勿因缺列重查。"
        "不明时先 list_datasets。"
    )
    return "\n".join(lines)


def format_prompt_catalog(session_id: str | None, *, tail: int = 8) -> str:
    """Compact catalog text for system-prompt injection (includes result_ref)."""
    return format_catalog_hint(session_id, tail=tail) if session_id else ""


def build_datasets_catalog(
    session_id: str | None,
    *,
    tail: int = 20,
    user_turn: int | None = None,
    current_user_turn: int | None = None,
) -> dict[str, Any]:
    """Structured catalog for list_datasets tool (newest first)."""
    meta: dict[str, Any] = {
        "session_id": session_id,
        "current_user_turn": current_user_turn,
        "tail": tail,
    }
    if not session_id:
        meta["hint"] = "无有效 session_id；请在本会话内先执行 query_data。"
        return {"datasets": [], "meta": meta}

    fetch_tail = max(tail * 5, tail) if user_turn is not None else tail
    rows = list_datasets(session_id, tail=min(fetch_tail, 200))
    if user_turn is not None:
        rows = [r for r in rows if r.user_turn == user_turn]
    rows = rows[-tail:]

    items: list[dict[str, Any]] = []
    for rec in reversed(rows):
        item: dict[str, Any] = {
            "dataset_id": rec.dataset_id,
            "result_ref": rec.result_ref,
            "user_turn": rec.user_turn,
            "result_rows": rec.result_rows,
            "query_limit": rec.query_limit,
            "rows_scanned": rec.rows_scanned,
            "resource": rec.resource,
            "classes": rec.classes,
            "grain": rec.grain or "row",
            "label": rec.label,
            "columns": rec.columns or rec.select_cols,
            "dimensions": rec.dimensions,
            "scope_hint": (
                f"limit={rec.query_limit}" if rec.query_limit is not None else "full_scan"
            ),
        }
        if rec.parent_dataset_id:
            item["parent_dataset_id"] = rec.parent_dataset_id
        if rec.source_result_ref:
            item["source_result_ref"] = rec.source_result_ref
        if current_user_turn is not None:
            item["is_current_turn"] = rec.user_turn == current_user_turn
        items.append(item)

    meta["count"] = len(items)
    if items:
        # Prefer newest raw row dataset for student-level follow-ups.
        row_pick = next((x for x in items if x.get("grain") == "row"), items[0])
        meta["next_step"] = {
            "tool": "aggregate_data",
            "examples": [
                {
                    "input": {"dataset_id": row_pick["dataset_id"]},
                    "bind": "chain",
                    "note": (
                        f"续算「{row_pick.get('label') or row_pick['dataset_id']}」"
                        f"（grain={row_pick.get('grain')}）；按学生须 grain=row"
                    ),
                },
            ],
        }
        meta["identity_hint"] = (
            "grain=row=原始提交行；grain=agg=已聚合表（通常无 student_ID）。"
            "agg 的 parent_dataset_id 指向上游 row；缺学号/学生级指标时用 parent，勿重查。"
            "教师说「刚才那份提交数据」时选 label 含「原始行」的 dataset_id。"
        )
    else:
        meta["hint"] = "尚无已登记数据集；请先 query_data，再 list_datasets 或 aggregate_data。"

    return {"datasets": items, "meta": meta}


def new_dataset_id() -> str:
    return f"ds_{uuid.uuid4().hex[:12]}"

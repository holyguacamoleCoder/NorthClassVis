"""File-backed persistence for chat sessions."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

from common.message import repair_stored_message
from common.paths import SESSIONS_DIR, bootstrap_agent_paths
from context.state import CompactState

from .models import ChatSession, SessionMeta

INDEX_FILE = "index.json"
ACTIVE_FILE = "active.json"
META_FILE = "meta.json"
MESSAGES_FILE = "messages.jsonl"
COMPACT_FILE = "compact.json"
TODO_FILE = "todo.json"
CONTEXT_FILE = "session_context.json"
FILTER_CONTEXT_FILE = "filter_context.json"


class FileSessionStore:
    def __init__(self, root: Path | None = None):
        if root is None:
            bootstrap_agent_paths()
        self.root = root or SESSIONS_DIR
        self.root.mkdir(parents=True, exist_ok=True)

    def _session_dir(self, session_id: str) -> Path:
        return self.root / session_id

    def list_meta(self) -> list[SessionMeta]:
        path = self.root / INDEX_FILE
        if not path.is_file():
            return []
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []
        if not isinstance(raw, list):
            return []
        items: list[SessionMeta] = []
        for x in raw:
            if not isinstance(x, dict):
                continue
            row = dict(x)
            if "user_turn_count" not in row and row.get("id"):
                row["user_turn_count"] = self._peek_user_turn_count(str(row["id"]))
            items.append(SessionMeta.from_dict(row))
        items.sort(key=lambda m: m.updated_at, reverse=True)
        return items

    def _peek_user_turn_count(self, session_id: str) -> int:
        meta_path = self._session_dir(session_id) / META_FILE
        if not meta_path.is_file():
            return 0
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            return int(meta.get("user_turn_count") or 0) if isinstance(meta, dict) else 0
        except (json.JSONDecodeError, OSError, TypeError, ValueError):
            return 0

    def _write_index(self, sessions: list[SessionMeta]) -> None:
        payload = [m.to_dict() for m in sorted(sessions, key=lambda m: m.updated_at, reverse=True)]
        (self.root / INDEX_FILE).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def get_active_id(self) -> str | None:
        path = self.root / ACTIVE_FILE
        if not path.is_file():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            sid = data.get("session_id")
            return str(sid) if sid else None
        except (json.JSONDecodeError, OSError, TypeError):
            return None

    def set_active_id(self, session_id: str | None) -> None:
        path = self.root / ACTIVE_FILE
        if session_id is None:
            path.unlink(missing_ok=True)
            return
        path.write_text(
            json.dumps({"session_id": session_id}, ensure_ascii=False),
            encoding="utf-8",
        )

    def load(self, session_id: str) -> ChatSession | None:
        sdir = self._session_dir(session_id)
        meta_path = sdir / META_FILE
        if not meta_path.is_file():
            return None
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
        if not isinstance(meta, dict):
            return None

        messages = self._load_messages(sdir / MESSAGES_FILE)
        compact = self._load_compact(sdir / COMPACT_FILE)
        session_context = self._load_context(sdir / CONTEXT_FILE)
        todo_items, todo_round = self._load_todo(sdir / TODO_FILE)
        filter_context = self._load_filter_context(sdir / FILTER_CONTEXT_FILE)

        return ChatSession(
            id=str(meta["id"]),
            title=str(meta.get("title") or "新对话"),
            permission_mode=str(meta.get("permission_mode") or "consult"),
            created_at=float(meta.get("created_at") or 0),
            updated_at=float(meta.get("updated_at") or 0),
            session_context=session_context,
            messages=messages,
            compact=compact,
            todo_items=todo_items,
            todo_round_since_update=todo_round,
            loaded_skills=[
                str(s) for s in (meta.get("loaded_skills") or []) if str(s).strip()
            ],
            loaded_references=[
                str(s) for s in (meta.get("loaded_references") or []) if str(s).strip()
            ],
            filter_context=filter_context,
            user_turn_count=int(meta.get("user_turn_count") or 0),
            messages_count=int(meta.get("messages_count") or 1),
        )

    def save(self, session: ChatSession) -> None:
        session.updated_at = time.time()
        sdir = self._session_dir(session.id)
        sdir.mkdir(parents=True, exist_ok=True)

        meta = {
            "id": session.id,
            "title": session.title,
            "permission_mode": session.permission_mode,
            "created_at": session.created_at,
            "updated_at": session.updated_at,
            "user_turn_count": session.user_turn_count,
            "messages_count": session.messages_count,
            "loaded_skills": list(session.loaded_skills or []),
            "loaded_references": list(session.loaded_references or []),
        }
        (sdir / META_FILE).write_text(
            json.dumps(meta, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self._save_messages(sdir / MESSAGES_FILE, session.messages)
        (sdir / COMPACT_FILE).write_text(
            json.dumps(
                {
                    "has_compacted": session.compact.has_compacted,
                    "last_summary": session.compact.last_summary,
                    "recent_files": list(session.compact.recent_files),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (sdir / CONTEXT_FILE).write_text(
            json.dumps(session.session_context, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (sdir / TODO_FILE).write_text(
            json.dumps(
                {
                    "items": session.todo_items,
                    "round_since_update": session.todo_round_since_update,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        if session.filter_context is not None:
            (sdir / FILTER_CONTEXT_FILE).write_text(
                json.dumps(session.filter_context, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        else:
            (sdir / FILTER_CONTEXT_FILE).unlink(missing_ok=True)

        index = {m.id: m for m in self.list_meta()}
        index[session.id] = session.meta
        self._write_index(list(index.values()))

    def delete(self, session_id: str) -> bool:
        sdir = self._session_dir(session_id)
        if not sdir.exists():
            return False
        import shutil

        shutil.rmtree(sdir, ignore_errors=True)
        index = [m for m in self.list_meta() if m.id != session_id]
        self._write_index(index)
        if self.get_active_id() == session_id:
            self.set_active_id(None)
        return True

    def new_id(self) -> str:
        return uuid4().hex[:12]

    @staticmethod
    def _load_messages(path: Path) -> list[dict[str, Any]]:
        if not path.is_file():
            return []
        messages: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                messages.append(repair_stored_message(row))
        return messages

    @staticmethod
    def _save_messages(path: Path, messages: list[dict[str, Any]]) -> None:
        with path.open("w", encoding="utf-8") as handle:
            for message in messages:
                row = repair_stored_message(message) if isinstance(message, dict) else message
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    @staticmethod
    def _load_compact(path: Path) -> CompactState:
        if not path.is_file():
            return CompactState()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return CompactState()
        if not isinstance(data, dict):
            return CompactState()
        return CompactState(
            has_compacted=bool(data.get("has_compacted")),
            last_summary=str(data.get("last_summary") or ""),
            recent_files=list(data.get("recent_files") or []),
        )

    @staticmethod
    def _load_context(path: Path) -> list[str]:
        if not path.is_file():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []
        if isinstance(data, list):
            return [str(x) for x in data if x]
        return []

    @staticmethod
    def _load_filter_context(path: Path) -> dict[str, Any] | None:
        if not path.is_file():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
        return data if isinstance(data, dict) else None

    @staticmethod
    def _load_todo(path: Path) -> tuple[list[dict[str, str]], int]:
        if not path.is_file():
            return [], 0
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return [], 0
        if not isinstance(data, dict):
            return [], 0
        items = data.get("items") or []
        if not isinstance(items, list):
            items = []
        return [x for x in items if isinstance(x, dict)], int(data.get("round_since_update") or 0)

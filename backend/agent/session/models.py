"""Chat session domain models (one conversation thread)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from context.state import CompactState


@dataclass
class SessionMeta:
    id: str
    title: str
    permission_mode: str
    created_at: float
    updated_at: float
    message_count: int = 0
    user_turn_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "permission_mode": self.permission_mode,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "message_count": self.message_count,
            "user_turn_count": self.user_turn_count,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SessionMeta:
        return cls(
            id=str(data["id"]),
            title=str(data.get("title") or "新对话"),
            permission_mode=str(data.get("permission_mode") or "consult"),
            created_at=float(data.get("created_at") or 0),
            updated_at=float(data.get("updated_at") or 0),
            message_count=int(data.get("message_count") or 0),
            user_turn_count=int(data.get("user_turn_count") or 0),
        )


@dataclass
class ChatSession:
    id: str
    title: str
    permission_mode: str
    created_at: float
    updated_at: float
    session_context: list[str] = field(default_factory=list)
    messages: list[dict[str, Any]] = field(default_factory=list)
    compact: CompactState = field(default_factory=CompactState)
    todo_items: list[dict[str, str]] = field(default_factory=list)
    todo_round_since_update: int = 0
    filter_context: dict[str, Any] | None = None
    # High-water user round index for logs / compaction; see count_user_turns().
    user_turn_count: int = 0
    messages_count: int = 1

    @property
    def meta(self) -> SessionMeta:
        from .turns import count_user_turns

        live_turns = count_user_turns(self.messages)
        return SessionMeta(
            id=self.id,
            title=self.title,
            permission_mode=self.permission_mode,
            created_at=self.created_at,
            updated_at=self.updated_at,
            message_count=len(self.messages),
            user_turn_count=max(self.user_turn_count, live_turns),
        )

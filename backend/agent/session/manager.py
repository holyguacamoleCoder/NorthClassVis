"""Orchestrate chat session lifecycle for the agent CLI / future HTTP API."""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from common.logger import get_logger, log_event
from context.state import CompactState
from data.filter_context import FilterContext, merge_defaults, merge_http_context
from hooks import HookManager
from loop_state import LoopState
from permission import CapabilityMode, PermissionManager
from tools.handlers.todo_write import apply_todo_snapshot, reset_todo_state

from .models import ChatSession, SessionMeta
from .store import FileSessionStore
from .turns import count_user_turns, resolve_loop_turn_count

if TYPE_CHECKING:
    from skills import SkillRegistry

_log = get_logger("session")

DEFAULT_TITLE = "新对话"
TITLE_MAX_LEN = 48


class SessionManager:
    """
    Owns the active chat session, persists to disk, and builds LoopState.

    Session storage is independent of the legacy Flask Orchestrator; HTTP can
    adopt this manager later without changing on-disk layout.
    """

    def __init__(
        self,
        store: FileSessionStore | None = None,
        *,
        hooks: HookManager | None = None,
        skills: SkillRegistry | None = None,
    ):
        self.store = store or FileSessionStore()
        self.hooks = hooks or HookManager()
        self.skills = skills
        self._active: ChatSession | None = None

    @property
    def active(self) -> ChatSession | None:
        return self._active

    def bootstrap(self, *, permission_mode: str = "consult") -> ChatSession:
        """Resume last active session from disk, or create a new one."""
        active_id = self.store.get_active_id()
        if active_id:
            loaded = self.store.load(active_id)
            if loaded is not None:
                self._activate(loaded, persist_active=False)
                log_event(
                    _log,
                    logging.INFO,
                    "session_resumed",
                    session_id=loaded.id,
                    messages=len(loaded.messages),
                    user_turn_count=loaded.user_turn_count,
                )
                return loaded
        return self.create_session(permission_mode=permission_mode)

    def create_session(
        self,
        *,
        permission_mode: str = "consult",
        title: str = DEFAULT_TITLE,
    ) -> ChatSession:
        if self._active is not None:
            self.persist_active()

        now = time.time()
        session_result = self.hooks.run_hooks(
            "SessionStart",
            {"tool_name": "", "tool_input": {}},
        )
        session = ChatSession(
            id=self.store.new_id(),
            title=title or DEFAULT_TITLE,
            permission_mode=permission_mode,
            created_at=now,
            updated_at=now,
            session_context=list(session_result.messages),
            messages=[],
            compact=CompactState(),
        )
        self._activate(session, persist_active=True)
        self.store.save(session)
        log_event(_log, logging.INFO, "session_created", session_id=session.id)
        return session

    def switch_session(self, session_id: str) -> ChatSession | None:
        if self._active and self._active.id == session_id:
            return self._active
        if self._active is not None:
            self.persist_active()

        loaded = self.store.load(session_id)
        if loaded is None:
            return None
        self._activate(loaded, persist_active=True)
        log_event(_log, logging.INFO, "session_switched", session_id=session_id)
        return loaded

    def list_sessions(self) -> list[SessionMeta]:
        return self.store.list_meta()

    def delete_session(self, session_id: str) -> bool:
        if self._active and self._active.id == session_id:
            self._active = None
            reset_todo_state()
        ok = self.store.delete(session_id)
        if ok and self.store.get_active_id() is None:
            remaining = self.store.list_meta()
            if remaining:
                self.switch_session(remaining[0].id)
        return ok

    def rename_active(self, title: str) -> bool:
        if not self._active or not title.strip():
            return False
        self._active.title = title.strip()[:200]
        self.store.save(self._active)
        return True

    def maybe_set_title_from_message(self, text: str) -> None:
        if not self._active or self._active.title != DEFAULT_TITLE:
            return
        snippet = " ".join(text.strip().split())
        if not snippet:
            return
        self._active.title = snippet[:TITLE_MAX_LEN]
        if len(snippet) > TITLE_MAX_LEN:
            self._active.title += "…"

    def persist_active(self) -> None:
        if self._active is None:
            return
        self._sync_todo_from_runtime()
        self.store.save(self._active)

    def set_filter_context(self, ctx: FilterContext) -> None:
        if self._active is None:
            return
        self._active.filter_context = ctx.to_dict()

    def apply_http_context(self, body: dict | None) -> FilterContext:
        """Map POST /api/agent/query context → session filter_context."""
        incoming = FilterContext.from_http_body(body)
        existing = FilterContext.from_dict(
            self._active.filter_context if self._active else None
        )
        merged = merge_http_context(existing, incoming)
        if merged is not None:
            self.set_filter_context(merged)
        return merge_defaults(
            FilterContext.from_dict(
                self._active.filter_context if self._active else None
            )
        )

    def restore_turn_snapshot(self, snapshot: dict) -> None:
        """Revert in-memory session to pre-turn state after user cancellation."""
        if self._active is None:
            return
        session = self._active
        session.messages = list(snapshot.get("messages") or [])
        session.title = str(snapshot.get("title") or session.title)
        session.todo_items = list(snapshot.get("todo_items") or [])
        session.todo_round_since_update = int(snapshot.get("todo_round_since_update") or 0)
        session.loaded_skills = list(snapshot.get("loaded_skills") or [])
        session.loaded_references = list(snapshot.get("loaded_references") or [])
        session.user_turn_count = int(snapshot.get("user_turn_count") or 0)
        reset_todo_state()
        if session.todo_items:
            apply_todo_snapshot(session.todo_items, session.todo_round_since_update)

    def capture_turn_snapshot(self) -> dict:
        if self._active is None:
            return {}
        session = self._active
        return {
            "messages": list(session.messages),
            "title": session.title,
            "todo_items": list(session.todo_items or []),
            "todo_round_since_update": session.todo_round_since_update,
            "loaded_skills": list(session.loaded_skills or []),
            "loaded_references": list(session.loaded_references or []),
            "user_turn_count": session.user_turn_count,
        }

    def sync_loop_state(self, loop_state: LoopState) -> None:
        """Copy in-memory loop fields back into the active session."""
        if self._active is None:
            return
        self._active.messages = list(loop_state.messages)
        self._active.compact = loop_state.compact
        self._active.session_context = list(loop_state.session_context)
        self._active.messages_count = loop_state.messages_count
        user_turns = count_user_turns(loop_state.messages)
        self._active.user_turn_count = max(self._active.user_turn_count, user_turns)
        if loop_state.permission is not None:
            self._active.permission_mode = loop_state.permission.mode.value
        if loop_state.filter_context is not None:
            self._active.filter_context = loop_state.filter_context.to_dict()
        self._active.loaded_skills = sorted(loop_state.loaded_skills)
        self._active.loaded_references = sorted(loop_state.loaded_references)

    def to_loop_state(self, permission: PermissionManager) -> LoopState:
        if self._active is None:
            raise RuntimeError("No active session")
        session = self._active
        permission.mode = CapabilityMode(session.permission_mode)
        fc = FilterContext.from_dict(session.filter_context)
        fc = merge_defaults(fc)
        return LoopState(
            messages=list(session.messages),
            compact=session.compact,
            permission=permission,
            hooks=self.hooks,
            session_context=list(session.session_context),
            skills=self.skills,
            session_id=session.id,
            turn_count=resolve_loop_turn_count(
                session.messages,
                stored_user_turn_count=session.user_turn_count,
            ),
            messages_count=session.messages_count,
            filter_context=fc,
            loaded_skills=set(session.loaded_skills or []),
            loaded_references=set(session.loaded_references or []),
        )

    def _activate(self, session: ChatSession, *, persist_active: bool) -> None:
        self._active = session
        reset_todo_state()
        if session.todo_items:
            apply_todo_snapshot(session.todo_items, session.todo_round_since_update)
        if persist_active:
            self.store.set_active_id(session.id)

    def _sync_todo_from_runtime(self) -> None:
        from tools.handlers.todo_write import export_todo_snapshot

        if self._active is None:
            return
        items, rounds = export_todo_snapshot()
        self._active.todo_items = items
        self._active.todo_round_since_update = rounds

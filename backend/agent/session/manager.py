"""Orchestrate chat session lifecycle for the agent CLI / future HTTP API."""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from common.logger import get_logger, log_event
from context.state import CompactState
from hooks import HookManager
from loop import LoopState
from permission import CapabilityMode, PermissionManager
from tools.todo_write import apply_todo_snapshot, reset_todo_state

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

    def to_loop_state(self, permission: PermissionManager) -> LoopState:
        if self._active is None:
            raise RuntimeError("No active session")
        session = self._active
        permission.mode = CapabilityMode(session.permission_mode)
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
        )

    def _activate(self, session: ChatSession, *, persist_active: bool) -> None:
        self._active = session
        reset_todo_state()
        if session.todo_items:
            apply_todo_snapshot(session.todo_items, session.todo_round_since_update)
        if persist_active:
            self.store.set_active_id(session.id)

    def _sync_todo_from_runtime(self) -> None:
        from tools.todo_write import export_todo_snapshot

        if self._active is None:
            return
        items, rounds = export_todo_snapshot()
        self._active.todo_items = items
        self._active.todo_round_since_update = rounds

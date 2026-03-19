from dataclasses import dataclass, field
from threading import Lock
from typing import Any, Dict, List, Optional

from agent.common.log_config import ensure_agent_logger

_agent_logger = ensure_agent_logger()

MEMORY_WINDOW_SIZE = 6


@dataclass
class TurnRecord:
    role: str
    text: str
    meta: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "role": self.role,
            "text": self.text,
            "meta": dict(self.meta or {}),
        }


@dataclass
class ConversationState:
    session_id: str
    turns: List[TurnRecord] = field(default_factory=list)
    pending_goal: Optional[Dict[str, Any]] = None
    needs_clarification: bool = False

    def recent_turns(self, size: int = MEMORY_WINDOW_SIZE) -> List[Dict[str, Any]]:
        if size <= 0:
            return []
        return [t.to_dict() for t in self.turns[-size:]]


class InMemoryConversationStore:
    """进程内会话记忆：滑动窗口 + 待补全 goal。"""

    def __init__(self, window_size: int = MEMORY_WINDOW_SIZE):
        self.window_size = max(1, int(window_size or MEMORY_WINDOW_SIZE))
        self._sessions: Dict[str, ConversationState] = {}
        self._lock = Lock()

    def resolve_session_id(self, context: Optional[dict]) -> str:
        ctx = context or {}
        sid = (
            ctx.get("session_id")
            or ctx.get("conversation_id")
            or ctx.get("chat_id")
            or "default"
        )
        sid = str(sid).strip() or "default"
        return sid

    def get_or_create(self, session_id: str) -> ConversationState:
        sid = str(session_id or "default")
        with self._lock:
            state = self._sessions.get(sid)
            if state is None:
                state = ConversationState(session_id=sid)
                self._sessions[sid] = state
                _agent_logger.debug("Memory create session=%s", sid)
            return state

    def append_turn(self, session_id: str, role: str, text: str, meta: Optional[dict] = None) -> None:
        state = self.get_or_create(session_id)
        state.turns.append(TurnRecord(role=role, text=(text or "").strip(), meta=dict(meta or {})))
        if len(state.turns) > self.window_size:
            state.turns = state.turns[-self.window_size :]
        _agent_logger.debug(
            "Memory append session=%s role=%s size=%d",
            session_id,
            role,
            len(state.turns),
        )

    def set_pending_goal(self, session_id: str, goal_dict: Optional[dict], needs_clarification: bool) -> None:
        state = self.get_or_create(session_id)
        state.pending_goal = dict(goal_dict or {}) if goal_dict else None
        state.needs_clarification = bool(needs_clarification and state.pending_goal)
        _agent_logger.debug(
            "Memory set_pending session=%s needs_clarification=%s has_goal=%s",
            session_id,
            state.needs_clarification,
            bool(state.pending_goal),
        )

    def build_runtime_context(self, base_context: Optional[dict], session_id: str) -> dict:
        ctx = dict(base_context or {})
        state = self.get_or_create(session_id)
        ctx["session_id"] = session_id
        ctx["recent_turns"] = state.recent_turns(self.window_size)
        recent_tool_results: List[Dict[str, Any]] = []
        for turn in state.turns[-self.window_size :]:
            meta = turn.meta or {}
            summary = meta.get("tool_execution_summary")
            if isinstance(summary, list):
                for item in summary:
                    if isinstance(item, dict):
                        recent_tool_results.append(dict(item))
        ctx["recent_tool_results"] = recent_tool_results
        if state.pending_goal and state.needs_clarification:
            ctx["pending_goal"] = dict(state.pending_goal)
        ctx["pending_needs_clarification"] = bool(state.needs_clarification)
        return ctx


_default_store: Optional[InMemoryConversationStore] = None


def get_default_memory_store() -> InMemoryConversationStore:
    global _default_store
    if _default_store is None:
        _default_store = InMemoryConversationStore(window_size=MEMORY_WINDOW_SIZE)
    return _default_store

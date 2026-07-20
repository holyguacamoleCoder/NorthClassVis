import sys
from pathlib import Path

import pytest

AGENT_DIR = Path(__file__).resolve().parents[1]
if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))

from context.state import CompactState
from session import FileSessionStore, SessionManager
from session.models import ChatSession
from tools.handlers.todo_write import export_todo_snapshot, reset_todo_state, run_todo_write


@pytest.fixture
def sessions_root(tmp_path):
    return tmp_path / ".sessions"


@pytest.fixture
def store(sessions_root):
    return FileSessionStore(sessions_root)


def test_store_roundtrip(store):
    session = ChatSession(
        id="abc123",
        title="测试会话",
        permission_mode="analyze",
        created_at=1000.0,
        updated_at=1001.0,
        session_context=["catalog block"],
        messages=[{"role": "user", "content": "hello"}],
        ui_messages=[
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi"},
        ],
        compact=CompactState(has_compacted=True, last_summary="sum", recent_files=["reports/a.md"]),
        todo_items=[{"content": "step1", "status": "pending"}],
        todo_round_since_update=2,
    )
    store.save(session)
    loaded = store.load("abc123")
    assert loaded is not None
    assert loaded.title == "测试会话"
    assert loaded.messages == session.messages
    assert loaded.ui_messages == session.ui_messages
    assert loaded.compact.has_compacted is True
    assert loaded.compact.recent_files == ["reports/a.md"]
    assert loaded.todo_items == session.todo_items
    assert loaded.todo_round_since_update == 2
    assert loaded.session_context == ["catalog block"]


def test_store_active_id(store):
    store.set_active_id("sess1")
    assert store.get_active_id() == "sess1"
    store.set_active_id(None)
    assert store.get_active_id() is None


def test_manager_create_switch_persist(sessions_root):
    mgr = SessionManager(store=FileSessionStore(sessions_root), hooks=__import__("hooks").HookManager())
    s1 = mgr.create_session(permission_mode="consult", title="first")
    s1.messages.append({"role": "user", "content": "q1"})
    mgr.persist_active()

    s2 = mgr.create_session(permission_mode="consult", title="second")
    assert s2.id != s1.id

    switched = mgr.switch_session(s1.id)
    assert switched is not None
    assert switched.title == "first"
    assert len(switched.messages) == 1

    reloaded = SessionManager(store=FileSessionStore(sessions_root), hooks=__import__("hooks").HookManager())
    resumed = reloaded.bootstrap(permission_mode="consult")
    assert resumed.id == s1.id
    assert len(resumed.messages) == 1


def test_manager_todo_snapshot_survives_switch(sessions_root):
    mgr = SessionManager(store=FileSessionStore(sessions_root), hooks=__import__("hooks").HookManager())
    mgr.create_session(title="todo-test")
    run_todo_write([{"content": "analyze csv", "status": "in_progress"}])
    mgr.persist_active()
    sid = mgr.active.id

    mgr.create_session(title="other")
    reset_todo_state()
    items, _ = export_todo_snapshot()
    assert items == []

    mgr.switch_session(sid)
    items, _ = export_todo_snapshot()
    assert len(items) == 1
    assert items[0]["content"] == "analyze csv"


def test_manager_delete_switches_to_remaining(sessions_root):
    store = FileSessionStore(sessions_root)
    mgr = SessionManager(store=store, hooks=__import__("hooks").HookManager())
    a = mgr.create_session(title="a")
    b = mgr.create_session(title="b")
    mgr.delete_session(a.id)
    assert mgr.active is not None
    assert mgr.active.id == b.id

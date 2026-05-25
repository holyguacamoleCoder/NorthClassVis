"""Tests for HTTP job cancellation and session rollback."""

from __future__ import annotations

import os
import sys
import threading

import pytest

_AGENT_ROOT = os.path.join(os.path.dirname(__file__), "..")
if _AGENT_ROOT not in sys.path:
    sys.path.insert(0, _AGENT_ROOT)

from cancel import TurnCancelled  # noqa: E402
from http_approval import ApprovalStore  # noqa: E402
from http_service import AgentHttpService, AgentJob, JobStatus  # noqa: E402
from loop import AgentLoop  # noqa: E402
from loop_state import LoopState  # noqa: E402
from permission import PermissionManager  # noqa: E402


def test_approval_store_cancel_pending_for_job():
    store = ApprovalStore()
    store.bind_job("job-1")
    approval_id = store.create_pending("write_file", {}, "test")
    assert store.cancel_pending_for_job("job-1") == 1
    allowed, _ = store.wait_decision(approval_id, timeout=0.5)
    assert allowed is False
    store.cleanup(approval_id)


def test_agent_loop_raises_on_should_cancel():
    state = LoopState(messages=[{"role": "user", "content": "hi"}])
    loop = AgentLoop(
        state,
        permission=PermissionManager(),
        should_cancel=lambda: True,
    )
    with pytest.raises(TurnCancelled):
        loop.run_loop()


def test_cancel_job_marks_request_and_blocks_terminal_states():
    svc = AgentHttpService.__new__(AgentHttpService)
    svc._jobs = {}
    svc._jobs_lock = threading.Lock()
    svc.approval_store = ApprovalStore()
    job = AgentJob(id="j1", session_id="s1", status=JobStatus.RUNNING)
    svc._jobs["j1"] = job
    assert svc.cancel_job("j1") is True
    assert job.cancel_requested is True
    assert svc.cancel_job("j1") is True
    job.status = JobStatus.COMPLETED
    assert svc.cancel_job("j1") is False


def test_session_restore_turn_snapshot():
    svc = AgentHttpService.get()
    session = svc.create_session(permission_mode="analyze", title="新对话")
    session_id = session["id"]
    svc.session_manager.active.messages = [{"role": "user", "content": "old"}]
    snap = svc.session_manager.capture_turn_snapshot()
    svc.session_manager.active.messages.append({"role": "user", "content": "new"})
    svc.session_manager.restore_turn_snapshot(snap)
    assert len(svc.session_manager.active.messages) == 1
    assert svc.session_manager.active.messages[0]["content"] == "old"
    svc.delete_session(session_id)

"""HTTP service: sessions, async jobs, AgentLoop execution."""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from uuid import uuid4

import runtime_bootstrap  # noqa: F401

from common.langfuse_tracing import user_turn_trace
from common.llm_client import LLMClient
from common.logger import get_logger, log_event
from common.memory import get_memory_manager
from common.paths import bootstrap_agent_paths
from hooks import HookManager
from loop import AgentLoop
from permission import CapabilityMode, PermissionManager
from session import SessionManager
from session.models import ChatSession
from session.ui_scope import augment_user_message_with_ui_scope
from skills import get_registry

from cancel import TurnCancelled
from .http_adapter import adapt_legacy_query_response, adapt_turn_response
from .http_approval import ApprovalStore, HttpApprovalHandler
from .http_progress import (
    empty_job_progress,
    make_job_progress_handler,
    merge_progress_patch,
    seed_job_progress_from_session,
)

_log = get_logger("agent_http")


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    AWAITING_APPROVAL = "awaiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class AgentJob:
    id: str
    session_id: str
    status: JobStatus = JobStatus.PENDING
    cancel_requested: bool = False
    approval: dict[str, Any] | None = None
    result: dict[str, Any] | None = None
    error: str | None = None
    progress: dict[str, Any] = field(default_factory=empty_job_progress)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


class AgentHttpService:
    _instance: AgentHttpService | None = None
    _init_lock = threading.Lock()

    @classmethod
    def get(cls) -> AgentHttpService:
        with cls._init_lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def __init__(self) -> None:
        bootstrap_agent_paths()
        get_memory_manager().load_all()
        self.hooks = HookManager()
        self.skills = get_registry()
        self.session_manager = SessionManager(hooks=self.hooks, skills=self.skills)
        self.session_manager.bootstrap(permission_mode="analyze")
        self.approval_store = ApprovalStore()
        self.approval_store.set_on_awaiting(self._on_job_awaiting_approval)
        self.llm_client = LLMClient()
        self._jobs: dict[str, AgentJob] = {}
        self._jobs_lock = threading.Lock()

    def _on_job_awaiting_approval(self, job_id: str, approval: dict[str, Any]) -> None:
        with self._jobs_lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            job.status = JobStatus.AWAITING_APPROVAL
            job.approval = approval
            job.updated_at = time.time()

    def _make_permission(self, mode: str | None = None) -> PermissionManager:
        parsed = CapabilityMode.ANALYZE
        if mode:
            try:
                parsed = CapabilityMode(str(mode).lower())
            except ValueError:
                parsed = CapabilityMode.ANALYZE
        handler = HttpApprovalHandler(self.approval_store)
        return PermissionManager(mode=parsed, approval=handler)

    def list_sessions(self) -> list[dict[str, Any]]:
        return [meta.to_dict() for meta in self.session_manager.list_sessions()]

    def get_active_session_id(self) -> str | None:
        active = self.session_manager.active
        if active is not None:
            return active.id
        return self.session_manager.store.get_active_id()

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        session = self._load_session(session_id)
        if session is None:
            return None
        return self._session_payload(session)

    def create_session(
        self,
        *,
        permission_mode: str = "analyze",
        title: str | None = None,
    ) -> dict[str, Any]:
        session = self.session_manager.create_session(
            permission_mode=permission_mode,
            title=title or "新对话",
        )
        return self._session_payload(session)

    def update_session(self, session_id: str, body: dict[str, Any]) -> dict[str, Any] | None:
        session = self._load_session(session_id)
        if session is None:
            return None
        if session_id != self.session_manager.active.id:
            self.session_manager.switch_session(session_id)
        if "title" in body and str(body["title"]).strip():
            self.session_manager.rename_active(str(body["title"]).strip())
        if "permission_mode" in body:
            mode = str(body["permission_mode"]).lower()
            try:
                CapabilityMode(mode)
                self.session_manager.active.permission_mode = mode
            except ValueError:
                pass
        self.session_manager.persist_active()
        return self._session_payload(self.session_manager.active)

    def delete_session(self, session_id: str) -> bool:
        return self.session_manager.delete_session(session_id)

    def switch_session(self, session_id: str) -> dict[str, Any] | None:
        loaded = self.session_manager.switch_session(session_id)
        if loaded is None:
            return None
        return self._session_payload(loaded)

    def submit_message(
        self,
        session_id: str,
        *,
        content: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        text = (content or "").strip()
        if not text:
            raise ValueError("message content is required")
        session = self._ensure_active(session_id)
        if context:
            self.session_manager.apply_http_context(context)
        job = AgentJob(
            id=uuid4().hex,
            session_id=session.id,
            progress=seed_job_progress_from_session(session),
        )
        with self._jobs_lock:
            self._jobs[job.id] = job
        thread = threading.Thread(
            target=self._run_job,
            args=(job.id, text),
            daemon=True,
        )
        thread.start()
        return {"job_id": job.id, "status": job.status.value, "session_id": session.id}

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        with self._jobs_lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            return self._job_payload(job)

    def cancel_job(self, job_id: str) -> bool:
        with self._jobs_lock:
            job = self._jobs.get(job_id)
            if job is None:
                return False
            if job.status in (
                JobStatus.COMPLETED,
                JobStatus.FAILED,
                JobStatus.CANCELLED,
            ):
                return False
            job.cancel_requested = True
            job.updated_at = time.time()
        self.approval_store.cancel_pending_for_job(job_id)
        log_event(_log, logging.INFO, "agent_job_cancel_requested", job_id=job_id)
        return True

    def resolve_approval(
        self,
        approval_id: str,
        *,
        decision: str,
        remember: bool = False,
    ) -> bool:
        normalized = decision.strip().lower()
        if normalized in ("allow", "allow_once", "y", "yes"):
            mapped = "allow_once"
        elif normalized in ("allow_always", "always"):
            mapped = "allow_always"
        else:
            mapped = "deny"
        ok = self.approval_store.resolve(approval_id, mapped, remember=remember)
        if ok:
            public = self.approval_store.get_public(approval_id)
            if public and public.get("job_id"):
                with self._jobs_lock:
                    job = self._jobs.get(str(public["job_id"]))
                    if job and job.status == JobStatus.AWAITING_APPROVAL:
                        job.status = JobStatus.RUNNING
                        job.approval = None
                        job.updated_at = time.time()
        return ok

    def query_legacy(self, question: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
        """One-shot query for POST /api/agent/query compatibility."""
        session = self.session_manager.active
        if session is None:
            session = self.session_manager.create_session(permission_mode="analyze")
        if context:
            self.session_manager.apply_http_context(context)
        continue_reason = self._execute_turn(session.id, question)[0]
        session = self.session_manager.active
        return adapt_legacy_query_response(
            session.messages,
            continue_reason=continue_reason,
        )

    def _run_job(self, job_id: str, content: str) -> None:
        with self._jobs_lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            job.status = JobStatus.RUNNING
            job.updated_at = time.time()
            session_id = job.session_id

        self.approval_store.bind_job(job_id)
        try:
            continue_reason, loaded_skills = self._execute_turn(
                session_id,
                content,
                job_id=job_id,
            )
            session = self.session_manager.active
            result = adapt_turn_response(
                session,
                continue_reason=continue_reason,
                loaded_skills=loaded_skills,
            )
            with self._jobs_lock:
                job = self._jobs.get(job_id)
                if job is None:
                    return
                if job.cancel_requested:
                    job.status = JobStatus.CANCELLED
                    job.updated_at = time.time()
                    return
                job.status = JobStatus.COMPLETED
                job.result = result
                job.updated_at = time.time()
        except TurnCancelled:
            log_event(_log, logging.INFO, "agent_job_cancelled", job_id=job_id)
            with self._jobs_lock:
                job = self._jobs.get(job_id)
                if job is None:
                    return
                job.status = JobStatus.CANCELLED
                job.updated_at = time.time()
        except Exception as exc:
            log_event(_log, logging.ERROR, "agent_job_failed", job_id=job_id, error=str(exc))
            with self._jobs_lock:
                job = self._jobs.get(job_id)
                if job is None:
                    return
                job.status = JobStatus.FAILED
                job.error = str(exc)
                job.updated_at = time.time()
        finally:
            self.approval_store.bind_job(None)

    def _patch_job_progress(self, job_id: str, patch: dict[str, Any]) -> None:
        with self._jobs_lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            merge_progress_patch(job.progress, patch)
            job.updated_at = patch.get("updated_at", time.time())

    def _job_cancel_checker(self, job_id: str | None):
        if not job_id:
            return None

        def should_cancel() -> bool:
            with self._jobs_lock:
                job = self._jobs.get(job_id)
                return job is not None and job.cancel_requested

        return should_cancel

    def _execute_turn(
        self,
        session_id: str,
        content: str,
        *,
        job_id: str | None = None,
    ) -> tuple[str | None, set[str]]:
        progress_cb = None
        if job_id:
            session = self.session_manager.active
            initial_skills = (
                list(session.loaded_skills) if session is not None else []
            )
            progress_cb = make_job_progress_handler(
                lambda patch: self._patch_job_progress(job_id, patch),
                initial_loaded_skills=initial_skills,
            )

        self._ensure_active(session_id)
        snapshot = self.session_manager.capture_turn_snapshot()
        should_cancel = self._job_cancel_checker(job_id)

        try:
            self.session_manager.maybe_set_title_from_message(content)
            perms = self._make_permission(self.session_manager.active.permission_mode)
            loop_state = self.session_manager.to_loop_state(perms)
            loop_state.analysis_context.session_id = loop_state.session_id
            loop_state.analysis_context.begin_user_turn(content)
            user_content = augment_user_message_with_ui_scope(
                content,
                loop_state.filter_context,
            )
            loop_state.messages.append({"role": "user", "content": user_content})

            with user_turn_trace(
                session_id=session_id,
                job_id=job_id,
                user_message=content,
                permission_mode=self.session_manager.active.permission_mode,
            ):
                agent_loop = AgentLoop(
                    loop_state,
                    llm_client=self.llm_client,
                    permission=perms,
                    hooks=self.hooks,
                    progress_callback=progress_cb,
                    should_cancel=should_cancel,
                )
                agent_loop.run_loop()
                if should_cancel and should_cancel():
                    raise TurnCancelled()
                continue_reason = loop_state.continue_reason
                loaded_skills = set(loop_state.loaded_skills)
                self.session_manager.sync_loop_state(loop_state)
                self.session_manager.persist_active()
                return continue_reason, loaded_skills
        except TurnCancelled:
            self.session_manager.restore_turn_snapshot(snapshot)
            self.session_manager.persist_active()
            raise

    def _ensure_active(self, session_id: str) -> ChatSession:
        active = self.session_manager.active
        if active is not None and active.id == session_id:
            return active
        loaded = self.session_manager.switch_session(session_id)
        if loaded is None:
            raise ValueError(f"session not found: {session_id}")
        return loaded

    def _load_session(self, session_id: str) -> ChatSession | None:
        if self.session_manager.active and self.session_manager.active.id == session_id:
            return self.session_manager.active
        return self.session_manager.store.load(session_id)

    def _session_payload(self, session: ChatSession) -> dict[str, Any]:
        from .http_adapter import serialize_messages

        return {
            "id": session.id,
            "title": session.title,
            "permission_mode": session.permission_mode,
            "created_at": session.created_at,
            "updated_at": session.updated_at,
            "message_count": len(session.messages),
            "messages": serialize_messages(session.messages),
            "todo_items": list(session.todo_items or []),
            "loaded_skills": list(session.loaded_skills or []),
            "filter_context": session.filter_context,
        }

    def _job_payload(self, job: AgentJob) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "job_id": job.id,
            "session_id": job.session_id,
            "status": job.status.value,
            "created_at": job.created_at,
            "updated_at": job.updated_at,
        }
        if job.approval:
            payload["approval"] = job.approval
        if job.result:
            payload["result"] = job.result
        if job.error:
            payload["error"] = job.error
        if job.status in (JobStatus.RUNNING, JobStatus.AWAITING_APPROVAL, JobStatus.COMPLETED):
            payload["progress"] = dict(job.progress or empty_job_progress())
        return payload

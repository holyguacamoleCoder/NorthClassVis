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
from common.llm_router import LLMRouter
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
from runs.registry import RunRegistry
from runs.derive import resolve_reaggregate_source
from runs.modify_resolver import resolve_modify_intent
from ..slash_commands import SlashCommand, execute_slash_command, list_skills_payload, parse_slash_command
from .adapter import adapt_legacy_query_response, adapt_turn_response, serialize_messages
from .approval import ApprovalStore, HttpApprovalHandler
from .progress import (
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
    derive_context: dict[str, Any] | None = None
    ui_scope: dict[str, Any] | None = None
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
        self.llm_router = LLMRouter.from_env()
        self.llm_client = self.llm_router.main
        self._jobs: dict[str, AgentJob] = {}
        self._jobs_lock = threading.Lock()
        self.run_registry = RunRegistry()

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

    def list_skills(self) -> list[dict[str, str]]:
        return list_skills_payload(self.skills)

    def list_memories(self) -> list[dict[str, Any]]:
        mgr = get_memory_manager()
        mgr.load_all()
        return mgr.list_entries()

    def get_memory(self, name: str) -> dict[str, Any] | None:
        mgr = get_memory_manager()
        mgr.load_all()
        return mgr.get_entry(name)

    def delete_memory(self, name: str) -> str:
        mgr = get_memory_manager()
        result = mgr.delete_entry(name)
        if not result.startswith("Error:"):
            mgr.load_all()
        return result

    def create_memory(
        self,
        name: str,
        *,
        description: str = "",
        mem_type: str = "user",
        content: str = "",
        enabled: bool = True,
    ) -> str:
        mgr = get_memory_manager()
        result = mgr.save_memory(
            name, description, mem_type, content, enabled=enabled
        )
        if not result.startswith("Error:"):
            mgr.load_all()
        return result

    def update_memory(
        self,
        name: str,
        *,
        content: str | None = None,
        description: str | None = None,
        mem_type: str | None = None,
        enabled: bool | None = None,
    ) -> str:
        mgr = get_memory_manager()
        result = mgr.update_entry(
            name,
            content=content,
            description=description,
            mem_type=mem_type,
            enabled=enabled,
        )
        if not result.startswith("Error:"):
            mgr.load_all()
        return result

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
        ctx = dict(context or {})
        from session.ui_scope import build_ui_scope_payload

        ui_scope = build_ui_scope_payload(ctx)
        ctx.pop("ui_scope", None)
        if ctx:
            self.session_manager.apply_http_context(ctx)

        slash = parse_slash_command(text)
        if slash is not None:
            return self._submit_slash_command(session, slash, user_line=text)

        job = AgentJob(
            id=uuid4().hex,
            session_id=session.id,
            progress=seed_job_progress_from_session(session),
            ui_scope=ui_scope,
        )
        derive_ctx: dict[str, Any] | None = None
        if ctx.get("derive_from_run_id"):
            derive_ctx = {
                "parent_run_id": str(ctx["derive_from_run_id"]),
                "patch": dict(ctx.get("patch") or {}),
                "source": "explicit",
            }
            job.derive_context = derive_ctx
        with self._jobs_lock:
            self._jobs[job.id] = job
        thread = threading.Thread(
            target=self._run_job,
            args=(job.id, text, derive_ctx),
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
        registry = getattr(self, "run_registry", None)
        if registry is not None:
            registry.request_cancel_for_job(job_id)
        log_event(_log, logging.INFO, "agent_job_cancel_requested", job_id=job_id)
        return True

    def list_session_runs(self, session_id: str, *, limit: int = 30) -> list[dict[str, Any]]:
        runs = self.run_registry.list_runs(session_id, limit=limit)
        return [run.to_dict() for run in runs]

    def get_tool_run(self, run_id: str) -> dict[str, Any] | None:
        run = self.run_registry.get_run(run_id)
        return run.to_dict() if run else None

    def cancel_tool_run(self, run_id: str) -> bool:
        return self.run_registry.cancel_run(run_id)

    def derive_tool_run(
        self,
        session_id: str,
        run_id: str,
        *,
        patch: dict[str, Any] | None = None,
        message: str = "请基于上次计算结果应用修改并重新分析。",
    ) -> dict[str, Any]:
        parent = self.run_registry.get_run(run_id)
        if parent is None or parent.session_id != session_id:
            raise ValueError("run not found for session")
        plan = self.run_registry.derive_run(run_id, dict(patch or {}))
        if plan is None:
            raise ValueError("cannot derive from run")
        context = {
            "derive_from_run_id": run_id,
            "patch": dict(patch or {}),
        }
        return self.submit_message(session_id, content=message, context=context)

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
        text = (question or "").strip()
        slash = parse_slash_command(text)
        if slash is not None:
            if session.id != self.session_manager.active.id:
                self.session_manager.switch_session(session.id)
            result = execute_slash_command(
                self.session_manager,
                self.skills,
                slash,
                user_line=text,
            )
            legacy = {
                k: result[k]
                for k in (
                    "answer",
                    "evidence",
                    "actions",
                    "visual_links",
                    "trace",
                    "goal_check",
                    "summary",
                )
                if k in result
            }
            return legacy
        continue_reason = self._execute_turn(session.id, question)[0]
        session = self.session_manager.active
        return adapt_legacy_query_response(
            session.messages,
            continue_reason=continue_reason,
            session_id=session.id,
        )

    def _submit_slash_command(
        self,
        session: ChatSession,
        command: SlashCommand,
        *,
        user_line: str,
    ) -> dict[str, Any]:
        """Run slash command synchronously; return a completed job envelope."""
        job = AgentJob(
            id=uuid4().hex,
            session_id=session.id,
            progress=seed_job_progress_from_session(session),
        )
        try:
            result = execute_slash_command(
                self.session_manager,
                self.skills,
                command,
                user_line=user_line,
            )
            job.status = JobStatus.COMPLETED
            job.result = result
            job.updated_at = time.time()
            if result.get("loaded_skills") is not None:
                merge_progress_patch(
                    job.progress,
                    {"loaded_skills": list(result["loaded_skills"])},
                )
            if result.get("loaded_references") is not None:
                merge_progress_patch(
                    job.progress,
                    {"loaded_references": list(result["loaded_references"])},
                )
            if result.get("todo_items") is not None:
                merge_progress_patch(
                    job.progress,
                    {"todo_items": list(result["todo_items"])},
                )
        except Exception as exc:
            job.status = JobStatus.FAILED
            job.error = str(exc)
            job.updated_at = time.time()
        with self._jobs_lock:
            self._jobs[job.id] = job
        return {
            "job_id": job.id,
            "status": job.status.value,
            "session_id": session.id,
        }

    def _run_job(self, job_id: str, content: str, derive_context: dict[str, Any] | None = None) -> None:
        with self._jobs_lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            job.status = JobStatus.RUNNING
            job.updated_at = time.time()
            session_id = job.session_id

        self.approval_store.bind_job(job_id)
        try:
            continue_reason, loaded_skills, loaded_references = self._execute_turn(
                session_id,
                content,
                job_id=job_id,
                derive_context=derive_context,
            )
            session = self.session_manager.active
            result = adapt_turn_response(
                session,
                continue_reason=continue_reason,
                loaded_skills=loaded_skills,
                loaded_references=loaded_references,
                run_registry=self.run_registry,
                job_id=job_id,
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
        derive_context: dict[str, Any] | None = None,
    ) -> tuple[str | None, set[str], set[str]]:
        progress_cb = None
        if job_id:
            session = self.session_manager.active
            initial_skills = (
                list(session.loaded_skills) if session is not None else []
            )
            initial_references = (
                list(session.loaded_references) if session is not None else []
            )
            progress_cb = make_job_progress_handler(
                lambda patch: self._patch_job_progress(job_id, patch),
                initial_loaded_skills=initial_skills,
                initial_loaded_references=initial_references,
            )

        self._ensure_active(session_id)
        snapshot = self.session_manager.capture_turn_snapshot()
        should_cancel = self._job_cancel_checker(job_id)

        try:
            from session.display import (
                append_ui_turn,
                ensure_ui_messages_seeded,
                extract_latest_turn_messages,
            )

            # Preserve teacher-visible history before this turn may macro-compact.
            ensure_ui_messages_seeded(self.session_manager.active)

            self.session_manager.maybe_set_title_from_message(content)
            perms = self._make_permission(self.session_manager.active.permission_mode)
            loop_state = self.session_manager.to_loop_state(perms)
            loop_state.analysis_context.session_id = loop_state.session_id
            loop_state.analysis_context.begin_user_turn(content)

            runs = self.run_registry.list_runs(session_id, limit=40)
            explicit_parent = (
                str(derive_context["parent_run_id"])
                if derive_context and derive_context.get("parent_run_id")
                else None
            )
            explicit_patch = (
                dict(derive_context.get("patch") or {})
                if derive_context
                else None
            )
            modify_hint = resolve_modify_intent(
                content,
                runs,
                explicit_parent_run_id=explicit_parent,
                explicit_patch=explicit_patch,
            )
            loop_state.modify_context = None
            if modify_hint:
                parent_run = self.run_registry.get_run(modify_hint.parent_run_id)
                plan = self.run_registry.derive_run(
                    modify_hint.parent_run_id,
                    modify_hint.patch,
                )
                reuse_ref, reuse_ds = None, None
                if plan:
                    reuse_ref = plan.reuse_result_ref
                    reuse_ds = plan.reuse_dataset_id
                if parent_run and not reuse_ref:
                    reuse_ref, reuse_ds = resolve_reaggregate_source(
                        parent_run,
                        self.run_registry,
                    )
                loop_state.modify_context = {
                    "parent_run_id": modify_hint.parent_run_id,
                    "patch": dict(modify_hint.patch or {}),
                    "strategy": plan.strategy if plan else None,
                    "parent_tool": modify_hint.parent_tool,
                    "parent_params": dict(parent_run.params) if parent_run else {},
                    "parent_result_ref": reuse_ref or (parent_run.result_ref if parent_run else None),
                    "parent_dataset_id": reuse_ds or (parent_run.dataset_id if parent_run else None),
                    "source": modify_hint.source,
                }

            user_content = augment_user_message_with_ui_scope(
                content,
                loop_state.filter_context,
            )
            loop_state.messages.append({"role": "user", "content": user_content})

            ui_scope = None
            if job_id:
                with self._jobs_lock:
                    job = self._jobs.get(job_id)
                    if job is not None:
                        ui_scope = job.ui_scope

            with user_turn_trace(
                session_id=session_id,
                job_id=job_id,
                user_message=content,
                permission_mode=self.session_manager.active.permission_mode,
            ):
                agent_loop = AgentLoop(
                    loop_state,
                    llm_router=self.llm_router,
                    permission=perms,
                    hooks=self.hooks,
                    progress_callback=progress_cb,
                    should_cancel=should_cancel,
                    run_registry=self.run_registry,
                    job_id=job_id,
                )
                agent_loop.run_loop()
                if should_cancel and should_cancel():
                    raise TurnCancelled()
                continue_reason = loop_state.continue_reason
                loaded_skills = set(loop_state.loaded_skills)
                loaded_references = set(loop_state.loaded_references)
                self.session_manager.sync_loop_state(loop_state)
                append_ui_turn(
                    self.session_manager.active,
                    display_user_text=content,
                    turn_messages=extract_latest_turn_messages(
                        list(loop_state.messages),
                        content,
                    ),
                    ui_scope=ui_scope,
                )
                self.session_manager.persist_active()
                return continue_reason, loaded_skills, loaded_references
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
        from session.display import messages_for_ui

        ui_msgs = messages_for_ui(session)
        return {
            "id": session.id,
            "title": session.title,
            "permission_mode": session.permission_mode,
            "created_at": session.created_at,
            "updated_at": session.updated_at,
            "message_count": len(ui_msgs),
            "messages": serialize_messages(ui_msgs),
            "todo_items": list(session.todo_items or []),
            "loaded_skills": list(session.loaded_skills or []),
            "loaded_references": list(session.loaded_references or []),
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


__all__ = ["AgentHttpService", "AgentJob", "JobStatus"]

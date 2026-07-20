"""Universal agent benchmark runner (elevated from binding online eval)."""

from __future__ import annotations

import concurrent.futures
import importlib
import json
import os
import shutil
import sys
import time
from pathlib import Path
from typing import Any, Callable

# Pin stdlib http before agent/http shadows it.
for _mod in ("http.client", "http.cookiejar"):
    if _mod not in sys.modules:
        importlib.import_module(_mod)

AGENT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))


def _load_backend_env() -> None:
    env_path = REPO_ROOT / "backend" / ".env"
    if not env_path.is_file():
        return
    try:
        from dotenv import load_dotenv

        load_dotenv(env_path, override=False)
        return
    except Exception:
        pass
    for line in env_path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text or text.startswith("#") or "=" not in text:
            continue
        key, _, val = text.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = val


_load_backend_env()

import runtime_bootstrap  # noqa: F401

os.environ.pop("BINDING_RESOLVER_DISABLE_LLM", None)

from common.llm_client import LLMClient  # noqa: E402
from common.paths import AGENT_STATE_DIR  # noqa: E402
from context.config import ContextCompactConfig  # noqa: E402
from data.dataset_registry import DatasetRecord, list_datasets  # noqa: E402
from data.filter_context import FilterContext, merge_defaults  # noqa: E402
from eval.metrics import evaluate_all  # noqa: E402
from eval.schema import Scenario  # noqa: E402
from eval.trace import (  # noqa: E402
    RunTrace,
    UsageStats,
    extract_tool_events,
    extract_user_contents,
    usage_from_sdk,
)
from hooks import HookManager  # noqa: E402
from loop import AgentLoop  # noqa: E402
from permission import CapabilityMode, PermissionManager  # noqa: E402
from permission.approval import DenyAskApprovalHandler  # noqa: E402
from session import SessionManager  # noqa: E402
from session.models import ChatSession  # noqa: E402
from session.store import FileSessionStore  # noqa: E402
from session.ui_scope import (  # noqa: E402
    augment_user_message_with_ui_scope,
    compose_llm_user_content,
    format_turn_scope_hint,
)
from skills import get_registry  # noqa: E402
from skills.message_meta import drop_previous_ui_scope_hints  # noqa: E402

EVAL_COMPACT_CONFIG = ContextCompactConfig(enabled=False)
SESSION_PREFIX = "agent-bench-"
RUN_TIMEOUT_SEC = 180


class UsageTracker:
    """Accumulate token usage by wrapping LLMClient.create_completion."""

    def __init__(self) -> None:
        self.stats = UsageStats()
        self._orig: Callable | None = None
        self._client: LLMClient | None = None

    def attach(self, client: LLMClient) -> None:
        self._client = client
        self._orig = client.create_completion

        def _wrapped(*args, **kwargs):
            resp = self._orig(*args, **kwargs)
            usage = getattr(resp, "usage", None) if resp is not None else None
            self.stats.add(usage_from_sdk(usage))
            return resp

        client.create_completion = _wrapped  # type: ignore[method-assign]

    def detach(self) -> None:
        if self._client is not None and self._orig is not None:
            self._client.create_completion = self._orig  # type: ignore[method-assign]


class _null_context:
    def __enter__(self):
        return None

    def __exit__(self, *args):
        return False


def _session_id(scenario_id: str, run_index: int) -> str:
    return f"{SESSION_PREFIX}{scenario_id}-r{run_index}"


def _cleanup_session(session_id: str) -> None:
    store = FileSessionStore()
    store.delete(session_id)
    path = AGENT_STATE_DIR / "sessions" / session_id
    if path.is_dir():
        shutil.rmtree(path, ignore_errors=True)


def _filter_context_from_dict(data: dict[str, Any] | None) -> FilterContext:
    if not data:
        return merge_defaults(FilterContext(classes=("Class1",), source="session"))
    fc = FilterContext(
        classes=tuple(data["classes"]) if data.get("classes") else None,
        majors=tuple(data["majors"]) if data.get("majors") else None,
        week_range=tuple(data["week_range"]) if data.get("week_range") else None,
        selected_student_ids=(
            tuple(data["selected_student_ids"]) if data.get("selected_student_ids") else None
        ),
        source="session",
    )
    return merge_defaults(fc)


def _activate_eval_session(
    manager: SessionManager,
    *,
    session_id: str,
    mode: str,
    filter_context: FilterContext,
) -> ChatSession:
    if manager.active is not None:
        manager.persist_active()
    now = time.time()
    session = ChatSession(
        id=session_id,
        title=f"agent-bench:{session_id}",
        permission_mode=mode,
        created_at=now,
        updated_at=now,
        session_context=[],
        messages=[],
        filter_context=filter_context.to_dict(),
    )
    manager.store.save(session)
    manager._activate(session, persist_active=True)  # noqa: SLF001
    return session


def _execute_turn(
    manager: SessionManager,
    llm_client: LLMClient,
    content: str,
    *,
    ui_scope: dict[str, Any] | None = None,
    eval_metadata: dict[str, Any] | None = None,
    benchmark_run_id: str | None = None,
) -> str | None:
    from session.display import (
        append_ui_turn,
        ensure_ui_messages_seeded,
        extract_latest_turn_messages,
    )

    perms = PermissionManager(
        mode=CapabilityMode(manager.active.permission_mode),
        approval=DenyAskApprovalHandler(),
    )
    # Teacher-visible transcript uses scenario turn text (not LLM-composed scope).
    ensure_ui_messages_seeded(manager.active)
    loop_state = manager.to_loop_state(perms)
    loop_state.analysis_context.session_id = loop_state.session_id
    loop_state.analysis_context.begin_user_turn(content)

    user_content = augment_user_message_with_ui_scope(content, loop_state.filter_context)
    loop_state.messages = drop_previous_ui_scope_hints(list(loop_state.messages))
    hint = format_turn_scope_hint(
        ui_scope=ui_scope,
        filter_context=loop_state.filter_context,
    )
    loop_state.messages.append(
        {
            "role": "user",
            "content": compose_llm_user_content(user_content, hint),
        }
    )

    try:
        from common.langfuse_tracing import user_turn_trace

        trace_kwargs: dict[str, Any] = {
            "session_id": loop_state.session_id,
            "job_id": None,
            "user_message": content,
            "permission_mode": manager.active.permission_mode,
        }
        meta = dict(eval_metadata or {})
        if benchmark_run_id:
            meta.setdefault("benchmark_run_id", benchmark_run_id)
        meta.setdefault("eval_kind", "agent_benchmark")
        trace_kwargs["extra_metadata"] = meta
        ctx = user_turn_trace(**trace_kwargs)
    except TypeError:
        ctx = _null_context()

    with ctx:
        agent_loop = AgentLoop(
            loop_state,
            llm_client=llm_client,
            permission=perms,
            hooks=manager.hooks,
            compact_config=EVAL_COMPACT_CONFIG,
        )
        agent_loop.run_loop()

    continue_reason = loop_state.continue_reason
    manager.sync_loop_state(loop_state)
    append_ui_turn(
        manager.active,
        display_user_text=content,
        turn_messages=extract_latest_turn_messages(
            list(loop_state.messages),
            content,
        ),
        ui_scope=ui_scope,
    )
    manager.persist_active()
    return continue_reason


def _dry_run_catalog() -> list[DatasetRecord]:
    return [
        DatasetRecord(
            dataset_id="ds_slice",
            result_ref="query-results/slice.json",
            user_turn=1,
            result_rows=10,
            query_limit=10,
            rows_scanned=20000,
            resource="submit_record",
        ),
        DatasetRecord(
            dataset_id="ds_broad",
            result_ref="query-results/broad.json",
            user_turn=1,
            result_rows=8000,
            query_limit=None,
            rows_scanned=8000,
            resource="submit_record",
        ),
    ]


def _agg_payload(*, narrow: bool, dataset_id: str, extra_meta: dict | None = None) -> str:
    rows = 10 if narrow else 8000
    ref = "query-results/slice.json" if narrow else "query-results/broad.json"
    meta = {
        "dataset_id": dataset_id,
        "result_ref": ref,
        "binding_decision": "auto:heuristic",
        "binding_trace": {"resolver": "heuristic"},
        "rows_scanned": rows,
    }
    if extra_meta:
        meta.update(extra_meta)
    return json.dumps(
        {
            "schema": [{"name": "n", "type": "integer"}, {"name": "avg", "type": "number"}],
            "rows": [[rows, 72.5]],
            "meta": meta,
        },
        ensure_ascii=False,
    )


def _append_tool(
    messages: list[dict[str, Any]],
    *,
    call_id: str,
    name: str,
    arguments: dict[str, Any],
    content: str,
) -> None:
    messages.append(
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": call_id,
                    "type": "function",
                    "function": {
                        "name": name,
                        "arguments": json.dumps(arguments, ensure_ascii=False),
                    },
                }
            ],
        }
    )
    messages.append({"role": "tool", "tool_call_id": call_id, "content": content})


def _dry_run_tool_payload(
    name: str,
    scenario: Scenario,
    turn_idx: int,
) -> tuple[dict[str, Any], str]:
    args: dict[str, Any] = {}
    content = '{"ok":true}'
    if name == "query_data":
        args = {"resource": "submit_record", "limit": 10, "class": "Class1"}
        for ea in scenario.expect_args:
            if ea.tool == "query_data" and (ea.turn_index in (None, turn_idx)):
                if ea.path == "limit" and ea.eq is not None:
                    args["limit"] = ea.eq
                elif ea.path == "class" and ea.eq is not None:
                    args["class"] = ea.eq
                elif ea.exists and ea.path:
                    parts = ea.path.split(".")
                    cur: Any = args
                    for p in parts[:-1]:
                        cur = cur.setdefault(p, {})
                    cur[parts[-1]] = "x"
        content = _agg_payload(narrow=True, dataset_id="ds_slice")
    elif name == "list_datasets":
        content = json.dumps(
            {"datasets": [{"dataset_id": "ds_slice", "result_rows": 10}]},
            ensure_ascii=False,
        )
    elif name == "enrich_data":
        args = {
            "input": {"dataset_id": "ds_slice"},
            "lookup": "title_info",
            "on": "title_ID",
            "columns": ["score"],
        }
        for ea in scenario.expect_args:
            if ea.tool == "enrich_data" and ea.eq is not None and ea.path:
                parts = ea.path.split(".")
                cur = args
                for p in parts[:-1]:
                    cur = cur.setdefault(p, {})
                cur[parts[-1]] = ea.eq
        content = _agg_payload(narrow=True, dataset_id="ds_enriched")
    elif name == "get_current_filter_context":
        content = json.dumps({"classes": ["Class1"]}, ensure_ascii=False)
    elif name == "inspect_schema":
        args = {"resource": "submit_record"}
        for ea in scenario.expect_args:
            if ea.tool == "inspect_schema" and ea.path == "resource" and ea.eq is not None:
                args["resource"] = ea.eq
        content = '{"columns":[{"name":"score"}]}'
    elif name == "aggregate_data":
        args = {
            "input": {"dataset_id": "ds_slice"},
            "metrics": [
                {"op": "count", "as": "n"},
                {"op": "mean", "field": "score", "as": "avg"},
            ],
        }
        content = _agg_payload(narrow=True, dataset_id="ds_slice")
    return args, content


def build_dry_run_messages(scenario: Scenario) -> list[dict[str, Any]]:
    """Synthetic transcript that satisfies declared expectations for --dry-run."""
    messages: list[dict[str, Any]] = []
    hint = format_turn_scope_hint(
        ui_scope=scenario.ui_scope,
        filter_context=_filter_context_from_dict(scenario.filter_context),
    )

    for turn_idx, text in enumerate(scenario.turns):
        messages.append(
            {
                "role": "user",
                "content": compose_llm_user_content(
                    text, hint if (turn_idx == 0 or scenario.ui_scope) else hint
                ),
            }
        )
        seq = 0

        # expect_task: inject tools on the declared user turn
        if scenario.expect_task:
            for a in scenario.expect_task.asserts:
                if a.kind not in ("tool_succeeded", "tool_called") or not a.tool:
                    continue
                if a.turn_index not in (None, turn_idx):
                    continue
                if any(
                    e.name == a.tool and e.turn_index == turn_idx
                    for e in extract_tool_events(messages)
                ):
                    continue
                seq += 1
                args, content = _dry_run_tool_payload(a.tool, scenario, turn_idx)
                _append_tool(
                    messages,
                    call_id=f"dry-{turn_idx}-taskpre-{seq}",
                    name=a.tool,
                    arguments=args,
                    content=content,
                )

        # Scope-required tools
        if scenario.expect_scope and scenario.expect_scope.must_call_tools:
            for tool in scenario.expect_scope.must_call_tools:
                seq += 1
                args, content = _dry_run_tool_payload(tool, scenario, turn_idx)
                _append_tool(
                    messages,
                    call_id=f"dry-{turn_idx}-scope-{seq}",
                    name=tool,
                    arguments=args,
                    content=content,
                )

        # expect_tools
        for exp in scenario.expect_tools:
            if exp.turn_index is not None and exp.turn_index != turn_idx:
                continue
            names = list(exp.names or exp.any_of[:1])
            while exp.min_count is not None and len(names) < exp.min_count:
                names.append("query_data")
            for name in names:
                if name == "aggregate_data" and any(
                    e.turn_index == turn_idx for e in scenario.expect_aggregates
                ):
                    continue
                seq += 1
                args, content = _dry_run_tool_payload(name, scenario, turn_idx)
                _append_tool(
                    messages,
                    call_id=f"dry-{turn_idx}-tool-{seq}",
                    name=name,
                    arguments=args,
                    content=content,
                )

        # expect_args-only tools (ensure call exists)
        for ea in scenario.expect_args:
            if ea.turn_index not in (None, turn_idx):
                continue
            if any(
                e.name == ea.tool and e.turn_index == turn_idx
                for e in extract_tool_events(messages)
            ):
                continue
            if ea.tool == "aggregate_data":
                continue
            seq += 1
            args, content = _dry_run_tool_payload(ea.tool, scenario, turn_idx)
            if ea.path and ea.eq is not None:
                parts = ea.path.split(".")
                cur: Any = args
                for p in parts[:-1]:
                    nxt: dict = {}
                    if p not in cur or not isinstance(cur.get(p), dict):
                        cur[p] = nxt
                    cur = cur[p]
                if isinstance(cur, dict):
                    cur[parts[-1]] = ea.eq
            _append_tool(
                messages,
                call_id=f"dry-{turn_idx}-arg-{seq}",
                name=ea.tool,
                arguments=args or {"resource": "submit_record"},
                content=content,
            )

        # Aggregates
        turn_exps = [e for e in scenario.expect_aggregates if e.turn_index == turn_idx]
        for exp in sorted(turn_exps, key=lambda e: e.ordinal or 1):
            seq += 1
            ordinal = exp.ordinal or 1
            call_id = f"dry-{turn_idx}-agg-{ordinal}"
            if exp.expect == "reject_cross_turn" or (scenario.expect_error and exp.expect_error):
                content = "Error: result_ref 来自上一轮提问，不能自动续用。"
                args = {"metrics": [{"op": "mean", "field": "score", "as": "avg"}]}
            elif exp.expect_error:
                content = "Error: guard"
                args = {"metrics": [{"op": "count", "as": "n"}]}
            else:
                is_narrow = exp.expect in (
                    "slice",
                    "explicit_dataset_id",
                    "allow_cross_turn_explicit",
                )
                ds_id = "ds_slice" if is_narrow else "ds_broad"
                content = _agg_payload(narrow=is_narrow, dataset_id=ds_id)
                args = {
                    "input": {"dataset_id": ds_id},
                    "metrics": [
                        {"op": "count", "as": "n"},
                        {"op": "mean", "field": "score", "as": "avg"},
                    ],
                }
            _append_tool(
                messages,
                call_id=call_id,
                name="aggregate_data",
                arguments=args,
                content=content,
            )

        # expect_error without aggregates
        if scenario.expect_error and not turn_exps and turn_idx == len(scenario.turns) - 1:
            seq += 1
            _append_tool(
                messages,
                call_id=f"dry-{turn_idx}-deny-{seq}",
                name="query_data",
                arguments={"resource": "submit_record"},
                content="Error: Permission denied — 模式限制，analyze 工具在 consult 不可用",
            )

        # Task asserts that need tools
        if scenario.expect_task and turn_idx == len(scenario.turns) - 1:
            for a in scenario.expect_task.asserts:
                tool = a.tool
                if a.kind in ("tool_succeeded", "tool_called") and tool:
                    if not any(e.name == tool for e in extract_tool_events(messages)):
                        seq += 1
                        args, content = _dry_run_tool_payload(tool, scenario, turn_idx)
                        _append_tool(
                            messages,
                            call_id=f"dry-{turn_idx}-task-{seq}",
                            name=tool,
                            arguments=args,
                            content=content,
                        )
            need_agg = any(
                a.kind in ("aggregate_has_metric", "numeric_in_tool_result", "tool_succeeded")
                and (a.tool in (None, "aggregate_data"))
                for a in scenario.expect_task.asserts
            )
            if need_agg and not any(
                e.name == "aggregate_data" for e in extract_tool_events(messages)
            ):
                seq += 1
                args, content = _dry_run_tool_payload("aggregate_data", scenario, turn_idx)
                # Prefer broad if expect_aggregates say so
                if any(e.expect == "broad" for e in scenario.expect_aggregates):
                    content = _agg_payload(narrow=False, dataset_id="ds_broad")
                    args = {
                        "input": {"dataset_id": "ds_broad"},
                        "metrics": [
                            {"op": "count", "as": "n"},
                            {"op": "mean", "field": "score", "as": "avg"},
                        ],
                    }
                _append_tool(
                    messages,
                    call_id=f"dry-{turn_idx}-task-agg",
                    name="aggregate_data",
                    arguments=args,
                    content=content,
                )

    return messages

def _should_keep_session(*, status: str, policy: str, dry_run: bool) -> bool:
    if dry_run or policy == "never":
        return False
    if policy == "always":
        return True
    # on-failure (default): keep failed / timeout / error for offline replay
    return status not in ("ok",)


def run_scenario(
    scenario: Scenario,
    *,
    run_index: int = 0,
    llm_client: LLMClient | None = None,
    dry_run: bool = False,
    timeout_sec: int = RUN_TIMEOUT_SEC,
    keep_session_policy: str = "on-failure",
    benchmark_run_id: str | None = None,
) -> RunTrace:
    session_id = _session_id(scenario.id, run_index)
    _cleanup_session(session_id)

    trace = RunTrace(
        scenario_id=scenario.id,
        run_index=run_index,
        session_id=session_id,
        dry_run=dry_run,
        benchmark_run_id=benchmark_run_id,
    )
    tracker = UsageTracker()
    t0 = time.time()

    try:
        if dry_run:
            messages = build_dry_run_messages(scenario)
            catalog = _dry_run_catalog()
            trace.usage = UsageStats(
                input_tokens=1200,
                output_tokens=300,
                cached_tokens=400 if run_index > 0 or "efficiency" in scenario.tags else 0,
                llm_calls=2,
            )
            continue_reason = None
        else:
            if llm_client is None or not llm_client.config.is_available():
                trace.status = "skipped"
                trace.error = "OPENAI_API_KEY not configured"
                return trace

            tracker.attach(llm_client)
            trace.provider_model = llm_client.config.model
            trace.provider_base_url = llm_client.config.base_url
            hooks = HookManager()
            manager = SessionManager(hooks=hooks, skills=get_registry())
            fc = _filter_context_from_dict(scenario.filter_context)
            _activate_eval_session(
                manager,
                session_id=session_id,
                mode=scenario.mode,
                filter_context=fc,
            )

            continue_reason = None
            for turn_idx, turn_text in enumerate(scenario.turns):
                tt0 = time.time()
                continue_reason = _execute_turn(
                    manager,
                    llm_client,
                    turn_text,
                    ui_scope=scenario.ui_scope,
                    eval_metadata={
                        "eval_kind": "agent_benchmark",
                        "benchmark_run_id": benchmark_run_id,
                        "scenario_id": scenario.id,
                        "run_index": run_index,
                        "turn_index": turn_idx,
                        "tags": scenario.tags,
                    },
                    benchmark_run_id=benchmark_run_id,
                )
                trace.turn_durations_sec.append(round(time.time() - tt0, 2))

            messages = list(manager.active.messages) if manager.active else []
            catalog = list_datasets(session_id, tail=200)
            trace.usage = tracker.stats

        trace.messages = messages
        trace.catalog = catalog
        trace.user_contents = extract_user_contents(messages)
        trace.tool_calls = extract_tool_events(
            messages,
            tool_results_dir=EVAL_COMPACT_CONFIG.tool_results_dir,
        )
        trace.continue_reason = continue_reason

        # Evaluate metrics
        results = evaluate_all(scenario, trace)
        hard = [r for r in results if r.hard_gate]
        if hard and not all(r.passed for r in hard):
            if trace.status == "ok":
                trace.status = "failed"

    except concurrent.futures.TimeoutError:
        trace.status = "timeout"
        trace.error = f"exceeded {timeout_sec}s"
        trace.failure_tags.append("llm_timeout")
    except Exception as exc:
        trace.status = "error"
        trace.error = str(exc)[:300]
    finally:
        trace.duration_sec = round(time.time() - t0, 2)
        tracker.detach()
        if not dry_run:
            keep = _should_keep_session(
                status=trace.status,
                policy=keep_session_policy,
                dry_run=dry_run,
            )
            trace.session_kept = keep
            if not keep:
                _cleanup_session(session_id)

    return trace


def run_with_timeout(fn: Callable[[], RunTrace], timeout: int) -> RunTrace:
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        fut = pool.submit(fn)
        try:
            return fut.result(timeout=timeout)
        except concurrent.futures.TimeoutError:
            return RunTrace(
                scenario_id="unknown",
                run_index=0,
                session_id="",
                status="timeout",
                error=f"exceeded {timeout}s",
                failure_tags=["llm_timeout"],
            )

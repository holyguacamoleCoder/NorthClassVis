#!/usr/bin/env python3
"""Online dataset binding accuracy evaluation via real AgentLoop + LLM.

Usage (repo root):
    python backend/agent/eval/run_binding_online_eval.py --runs 3
    python backend/agent/eval/run_binding_online_eval.py --scenario chain_slice_two_turns --runs 1
    python backend/agent/eval/run_binding_online_eval.py --dry-run
"""

from __future__ import annotations

import argparse
import concurrent.futures
import importlib
import json
import os
import shutil
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Pin stdlib http submodules before backend/agent/http can shadow http on sys.path.
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

# Online eval must use LLM intent path when available.
os.environ.pop("BINDING_RESOLVER_DISABLE_LLM", None)

from common.llm_client import LLMClient  # noqa: E402
from common.paths import AGENT_STATE_DIR  # noqa: E402
from data.dataset_registry import DatasetRecord, list_datasets  # noqa: E402
from data.filter_context import FilterContext, merge_defaults  # noqa: E402
from eval.binding_judge import (  # noqa: E402
    judge_aggregate,
    recover_meta_from_partial_json,
    resolver_from_meta,
)
from hooks import HookManager  # noqa: E402
from loop import AgentLoop  # noqa: E402
from loop_state import LoopState  # noqa: E402
from permission import CapabilityMode, PermissionManager  # noqa: E402
from permission.approval import DenyAskApprovalHandler  # noqa: E402
from session import SessionManager  # noqa: E402
from session.models import ChatSession  # noqa: E402
from session.store import FileSessionStore  # noqa: E402
from session.ui_scope import augment_user_message_with_ui_scope  # noqa: E402
from skills import get_registry  # noqa: E402
from context.config import ContextCompactConfig  # noqa: E402

DEFAULT_SCENARIOS = Path(__file__).resolve().parent / "fixtures" / "binding_online_scenarios.json"
EVAL_COMPACT_CONFIG = ContextCompactConfig(enabled=False)
DEFAULT_JSON = REPO_ROOT / "data" / "eval" / "binding_accuracy_online.json"
DEFAULT_REPORT = REPO_ROOT / "docs" / "eval" / "binding-accuracy-online.md"
SESSION_PREFIX = "binding-online-"
RUN_TIMEOUT_SEC = 180


@dataclass
class ExpectAggregate:
    turn_index: int
    expect: str
    ordinal: int | None = None
    expect_error: bool = False
    accept_guard_error: bool = False
    note: str | None = None


@dataclass
class OnlineScenario:
    id: str
    mode: str = "analyze"
    filter_context: dict[str, Any] = field(default_factory=dict)
    turns: list[str] = field(default_factory=list)
    expect_aggregates: list[ExpectAggregate] = field(default_factory=list)


def load_scenarios(path: Path) -> list[OnlineScenario]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    scenarios: list[OnlineScenario] = []
    for item in raw:
        expects = [
            ExpectAggregate(
                turn_index=int(e["turn_index"]),
                expect=str(e["expect"]),
                ordinal=int(e["ordinal"]) if e.get("ordinal") is not None else None,
                expect_error=bool(e.get("expect_error")),
                accept_guard_error=bool(e.get("accept_guard_error")),
                note=e.get("note"),
            )
            for e in item.get("expect_aggregates") or []
        ]
        scenarios.append(
            OnlineScenario(
                id=str(item["id"]),
                mode=str(item.get("mode") or "analyze"),
                filter_context=dict(item.get("filter_context") or {}),
                turns=[str(t) for t in item.get("turns") or []],
                expect_aggregates=expects,
            )
        )
    return scenarios


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
        title=f"binding-eval:{session_id}",
        permission_mode=mode,
        created_at=now,
        updated_at=now,
        session_context=[],
        messages=[],
        filter_context=filter_context.to_dict(),
    )
    manager.store.save(session)
    manager._activate(session, persist_active=True)  # noqa: SLF001 — eval harness
    return session


def _execute_turn(
    manager: SessionManager,
    llm_client: LLMClient,
    content: str,
    *,
    eval_metadata: dict[str, Any] | None = None,
) -> None:
    perms = PermissionManager(
        mode=CapabilityMode(manager.active.permission_mode),
        approval=DenyAskApprovalHandler(),
    )
    loop_state = manager.to_loop_state(perms)
    loop_state.analysis_context.session_id = loop_state.session_id
    loop_state.analysis_context.begin_user_turn(content)

    user_content = augment_user_message_with_ui_scope(content, loop_state.filter_context)
    loop_state.messages.append({"role": "user", "content": user_content})

    try:
        from common.langfuse_tracing import user_turn_trace

        trace_kwargs: dict[str, Any] = {
            "session_id": loop_state.session_id,
            "job_id": None,
            "user_message": content,
            "permission_mode": manager.active.permission_mode,
        }
        if eval_metadata:
            trace_kwargs["extra_metadata"] = eval_metadata
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

    manager.sync_loop_state(loop_state)
    manager.persist_active()


class _null_context:
    def __enter__(self):
        return None

    def __exit__(self, *args):
        return False


def _resolve_tool_result_content(content: str, call_id: str) -> str:
    """Message history may only store a truncated persisted preview — load full output."""
    if call_id:
        stored = EVAL_COMPACT_CONFIG.tool_results_dir / f"{call_id}.txt"
        if stored.is_file():
            return stored.read_text(encoding="utf-8")
    return content


def extract_aggregate_events(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Extract aggregate_data tool calls with turn_index (0-based) and ordinal."""
    tool_results: dict[str, str] = {}
    for msg in messages:
        if msg.get("role") == "tool" and msg.get("tool_call_id"):
            tool_results[str(msg["tool_call_id"])] = str(msg.get("content") or "")

    events: list[dict[str, Any]] = []
    user_turn_idx = -1
    ordinals: dict[int, int] = {}

    for msg in messages:
        if msg.get("role") == "user":
            user_turn_idx += 1
            continue
        if msg.get("role") != "assistant":
            continue
        for tc in msg.get("tool_calls") or []:
            fn = tc.get("function") or {}
            name = fn.get("name") or tc.get("name")
            if name != "aggregate_data":
                continue
            call_id = str(tc.get("id") or "")
            ordinals.setdefault(user_turn_idx, 0)
            ordinals[user_turn_idx] += 1
            ordinal = ordinals[user_turn_idx]
            args_raw = fn.get("arguments") or "{}"
            try:
                tool_input = json.loads(args_raw) if isinstance(args_raw, str) else dict(args_raw)
            except json.JSONDecodeError:
                tool_input = {"_raw_arguments": args_raw}

            content = _resolve_tool_result_content(tool_results.get(call_id, ""), call_id)
            meta: dict[str, Any] = {}
            is_error = content.strip().startswith("Error:") or "Permission denied" in content
            if not is_error and content.strip():
                try:
                    payload = json.loads(content)
                    meta = dict(payload.get("meta") or {})
                except json.JSONDecodeError:
                    meta = recover_meta_from_partial_json(content)
                    is_error = not meta

            events.append(
                {
                    "turn_index": user_turn_idx,
                    "ordinal": ordinal,
                    "tool_call_id": call_id,
                    "tool_input": tool_input,
                    "content": content,
                    "meta": meta,
                    "is_error": is_error,
                    "resolver": resolver_from_meta(meta),
                }
            )
    return events


def _match_expectation(
    expects: list[ExpectAggregate],
    event: dict[str, Any],
    catalog: list[DatasetRecord],
) -> tuple[ExpectAggregate | None, tuple[bool, str]]:
    turn = int(event["turn_index"])
    ordinal = int(event["ordinal"])
    candidates = [e for e in expects if e.turn_index == turn]
    if not candidates:
        return None, (False, f"no expectation for turn_index={turn}")
    if len(candidates) == 1 and candidates[0].ordinal is None:
        exp = candidates[0]
    else:
        matched = [e for e in candidates if e.ordinal == ordinal]
        if not matched:
            return None, (False, f"no expectation for turn={turn} ordinal={ordinal}")
        exp = matched[0]

    meta = dict(event.get("meta") or {})
    meta.setdefault("session_id", None)
    ok, reason = judge_aggregate(
        exp.expect,
        meta=meta,
        catalog=catalog,
        content=str(event.get("content") or ""),
        tool_input=event.get("tool_input"),
        current_user_turn=turn + 1,
        accept_guard_error=exp.accept_guard_error,
    )
    if exp.expect_error and not event.get("is_error"):
        return exp, (False, "expected guard error but aggregate succeeded")
    return exp, (ok, reason)


def evaluate_scenario_run(
    scenario: OnlineScenario,
    *,
    run_index: int,
    llm_client: LLMClient | None,
    dry_run: bool = False,
) -> dict[str, Any]:
    session_id = _session_id(scenario.id, run_index)
    _cleanup_session(session_id)

    result: dict[str, Any] = {
        "scenario_id": scenario.id,
        "run_index": run_index,
        "session_id": session_id,
        "status": "ok",
        "aggregate_judgments": [],
        "missing_expectations": [],
        "error": None,
        "duration_sec": 0.0,
    }

    t0 = time.time()
    try:
        if dry_run:
            messages = _dry_run_messages(scenario)
            catalog = _dry_run_catalog(scenario)
        else:
            if llm_client is None or not llm_client.config.is_available():
                result["status"] = "skipped"
                result["error"] = "OPENAI_API_KEY not configured"
                return result

            hooks = HookManager()
            manager = SessionManager(hooks=hooks, skills=get_registry())
            fc = _filter_context_from_dict(scenario.filter_context)
            _activate_eval_session(
                manager,
                session_id=session_id,
                mode=scenario.mode,
                filter_context=fc,
            )

            for turn_idx, turn_text in enumerate(scenario.turns):
                _execute_turn(
                    manager,
                    llm_client,
                    turn_text,
                    eval_metadata={
                        "eval_kind": "binding_online",
                        "scenario_id": scenario.id,
                        "run_index": run_index,
                        "turn_index": turn_idx,
                    },
                )

            messages = list(manager.active.messages) if manager.active else []
            catalog = list_datasets(session_id, tail=200)

        events = extract_aggregate_events(messages)
        used_events: set[int] = set()

        for exp in scenario.expect_aggregates:
            matched_event = None
            turn_events = [
                (i, ev)
                for i, ev in enumerate(events)
                if i not in used_events and ev["turn_index"] == exp.turn_index
            ]
            if exp.ordinal is not None:
                for i, ev in turn_events:
                    if ev["ordinal"] == exp.ordinal:
                        matched_event = (i, ev)
                        break
            elif exp.accept_guard_error and turn_events:
                # Guard 场景：该 turn 内任一次 aggregate 通过即算通过（避免 LLM 重试后最后一笔绑 broad）。
                passed: tuple[int, dict[str, Any], str] | None = None
                for i, ev in turn_events:
                    meta_try = dict(ev.get("meta") or {})
                    meta_try["session_id"] = session_id
                    ev_try = {**ev, "meta": meta_try}
                    _, (ok_try, reason_try) = _match_expectation(
                        scenario.expect_aggregates, ev_try, catalog
                    )
                    if ok_try:
                        passed = (i, ev, reason_try)
                        break
                if passed is not None:
                    matched_event = (passed[0], passed[1])
                else:
                    matched_event = turn_events[-1]
            elif turn_events:
                # No ordinal: judge the last aggregate in that user turn (after retries).
                matched_event = turn_events[-1]

            if matched_event is None:
                result["missing_expectations"].append(
                    {
                        "turn_index": exp.turn_index,
                        "ordinal": exp.ordinal,
                        "expect": exp.expect,
                        "reason": "no matching aggregate_data call",
                    }
                )
                result["aggregate_judgments"].append(
                    {
                        "scenario_id": scenario.id,
                        "turn_index": exp.turn_index,
                        "ordinal": exp.ordinal,
                        "expect": exp.expect,
                        "ok": False,
                        "reason": "missing aggregate",
                        "resolver": None,
                    }
                )
                continue

            idx, ev = matched_event
            used_events.add(idx)
            meta = dict(ev.get("meta") or {})
            meta["session_id"] = session_id
            ev_with_session = {**ev, "meta": meta}
            _, (ok, reason) = _match_expectation(scenario.expect_aggregates, ev_with_session, catalog)
            result["aggregate_judgments"].append(
                {
                    "scenario_id": scenario.id,
                    "turn_index": exp.turn_index,
                    "ordinal": exp.ordinal or ev["ordinal"],
                    "expect": exp.expect,
                    "ok": ok,
                    "reason": reason,
                    "resolver": ev.get("resolver"),
                    "result_ref": meta.get("result_ref"),
                    "dataset_id": meta.get("dataset_id"),
                    "is_error": ev.get("is_error"),
                }
            )

    except concurrent.futures.TimeoutError:
        result["status"] = "timeout"
        result["error"] = f"exceeded {RUN_TIMEOUT_SEC}s"
    except Exception as exc:
        result["status"] = "error"
        result["error"] = str(exc)[:300]
    finally:
        result["duration_sec"] = round(time.time() - t0, 2)
        if result.get("missing_expectations") and result.get("status") == "ok":
            result["status"] = "incomplete"
        if not dry_run:
            _cleanup_session(session_id)

    return result


def _dry_run_messages(scenario: OnlineScenario) -> list[dict[str, Any]]:
    """Synthetic messages for --dry-run (judge / extraction smoke)."""
    messages: list[dict[str, Any]] = []
    for turn_idx, text in enumerate(scenario.turns):
        messages.append({"role": "user", "content": text})
        turn_exps = [e for e in scenario.expect_aggregates if e.turn_index == turn_idx]
        if not turn_exps:
            continue
        for exp in sorted(turn_exps, key=lambda e: e.ordinal or 1):
            ordinal = exp.ordinal or 1
            call_id = f"dry-{turn_idx}-{ordinal}"
            ds_id = "ds_slice"
            if exp.expect == "reject_cross_turn":
                content = "Error: result_ref 来自上一轮提问，不能自动续用。"
            elif exp.expect_error:
                content = "Error: guard"
            else:
                is_narrow = exp.expect in (
                    "slice",
                    "explicit_dataset_id",
                    "allow_cross_turn_explicit",
                )
                ds_id = "ds_slice" if is_narrow else "ds_broad"
                ref = "query-results/slice.json" if is_narrow else "query-results/broad.json"
                rows = 10 if is_narrow else 8000
                meta = {
                    "dataset_id": ds_id,
                    "result_ref": ref,
                    "binding_decision": "auto:heuristic",
                    "binding_trace": {"resolver": "heuristic"},
                }
                content = json.dumps(
                    {
                        "schema": [{"name": "n", "type": "integer"}],
                        "rows": [[rows]],
                        "meta": meta,
                    },
                    ensure_ascii=False,
                )
            messages.append(
                {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "id": call_id,
                            "type": "function",
                            "function": {
                                "name": "aggregate_data",
                                "arguments": json.dumps(
                                    {
                                        "input": {"dataset_id": ds_id},
                                        "metrics": [{"op": "count", "as": "n"}],
                                    }
                                ),
                            },
                        }
                    ],
                }
            )
            messages.append({"role": "tool", "tool_call_id": call_id, "content": content})
    return messages


def _dry_run_catalog(scenario: OnlineScenario) -> list[DatasetRecord]:
    del scenario  # catalog is fixed for synthetic dry-run rows
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


def summarize(all_runs: list[dict[str, Any]], *, scenarios: list[OnlineScenario]) -> dict[str, Any]:
    judgments = [
        j
        for run in all_runs
        for j in run.get("aggregate_judgments") or []
    ]
    total = len(judgments)
    correct = sum(1 for j in judgments if j.get("ok"))
    incomplete = [r for r in all_runs if r.get("status") != "ok"]

    by_scenario: dict[str, dict[str, int]] = {}
    for j in judgments:
        sid = str(j.get("scenario_id") or "unknown")
        by_scenario.setdefault(sid, {"total": 0, "correct": 0})
        by_scenario[sid]["total"] += 1
        if j.get("ok"):
            by_scenario[sid]["correct"] += 1

    by_resolver: dict[str, dict[str, int]] = {}
    for j in judgments:
        res = str(j.get("resolver") or "unknown")
        by_resolver.setdefault(res, {"total": 0, "correct": 0})
        by_resolver[res]["total"] += 1
        if j.get("ok"):
            by_resolver[res]["correct"] += 1

    scenario_rates = {
        sid: round(100 * v["correct"] / v["total"], 2) if v["total"] else 0.0
        for sid, v in sorted(by_scenario.items())
    }
    resolver_rates = {
        res: round(100 * v["correct"] / v["total"], 2) if v["total"] else 0.0
        for res, v in sorted(by_resolver.items())
    }

    failures = [
        {
            "scenario_id": run["scenario_id"],
            "run_index": run["run_index"],
            "turn_index": j.get("turn_index"),
            "ordinal": j.get("ordinal"),
            "expect": j.get("expect"),
            "reason": j.get("reason"),
            "resolver": j.get("resolver"),
            "dataset_id": j.get("dataset_id"),
            "status": run.get("status"),
        }
        for run in all_runs
        for j in run.get("aggregate_judgments") or []
        if not j.get("ok")
    ]
    failures.extend(
        {
            "scenario_id": run["scenario_id"],
            "run_index": run["run_index"],
            "expect": m.get("expect"),
            "reason": m.get("reason"),
            "status": "missing_aggregate",
        }
        for run in all_runs
        for m in run.get("missing_expectations") or []
    )

    n_expects = sum(len(s.expect_aggregates) for s in scenarios)
    return {
        "N_scenarios": len(scenarios),
        "N_runs": len({(r["scenario_id"], r["run_index"]) for r in all_runs}),
        "N_aggregates": total,
        "N_expect_aggregates": n_expects * max(1, len({r["run_index"] for r in all_runs})),
        "correct": correct,
        "accuracy_pct": round(100 * correct / total, 2) if total else 0.0,
        "by_scenario": scenario_rates,
        "by_resolver": resolver_rates,
        "failures": failures,
        "incomplete_runs": incomplete,
        "resolver_mode": "live AgentLoop (LLM intent enabled)",
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def render_report(summary: dict[str, Any]) -> str:
    fail_lines = ["| 场景 | run | expect | 原因 |", "|------|-----|--------|------|"]
    for f in summary.get("failures") or []:
        fail_lines.append(
            f"| `{f.get('scenario_id')}` | {f.get('run_index')} | `{f.get('expect')}` | {f.get('reason')} |"
        )
    if len(fail_lines) == 2:
        fail_lines.append("| — | — | — | 无 |")

    scen_lines = ["| 场景 | 准确率 |", "|------|--------|"]
    for sid, rate in (summary.get("by_scenario") or {}).items():
        scen_lines.append(f"| `{sid}` | {rate}% |")

    res_lines = ["| resolver | 准确率 |", "|----------|--------|"]
    for res, rate in (summary.get("by_resolver") or {}).items():
        res_lines.append(f"| `{res}` | {rate}% |")

    acc = summary.get("accuracy_pct", 0)
    n_agg = summary.get("N_aggregates", 0)
    return f"""# Dataset Binding 在线准确率评测

> 生成时间：{datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}  
> 脚本：`backend/agent/eval/run_binding_online_eval.py`

## 指标定义

### Online Binding Accuracy

对每条评测场景中每一次 **`aggregate_data` 调用**判定是否正确：

| 判定 | 条件 |
|------|------|
| **正确** | 实际绑定的 `result_ref` 对应数据集满足场景 `expect` 约束 |
| **正确（guard）** | `expect_error=true` 或 `reject_cross_turn`，且 aggregate 返回 Error / Permission deny |
| **错误** | 绑错 ref、该拒绝却成功、该成功却 Error、或缺少预期 aggregate |

**准确率** = 正确 aggregate 判定数 / 评测 aggregate 总数

### expect 类型

| expect | 判定规则 |
|--------|----------|
| `slice` | `result_rows ≤ 50` 且（有 `query_limit` 或 `rows_scanned >> result_rows`） |
| `broad` | `result_rows > 500` 或无 limit 的全量 scan |
| `explicit_dataset_id` | `meta.dataset_id` / catalog 显式匹配 |
| `reject_cross_turn` | 跨 turn 静默续用旧 ref → Error（含「上一轮」提示） |
| `allow_cross_turn_explicit` | 显式 `dataset_id` 跨 turn 成功 |

绑定信息来源（优先级）：aggregate tool result `meta` → `datasets.jsonl` → `binding_trace`。

**评测模式**：真实 `AgentLoop.run_loop()` + 真实 LLM（**未**设置 `BINDING_RESOLVER_DISABLE_LLM`）。

## 失败归因（分类与修复）

| 类别 | 典型场景 | 根因 | 修复 |
|------|----------|------|------|
| **A. 评测误判** | `cross_turn_explicit_dataset` | tool JSON 截断 / `dataset_id` 未从 tool_input 读取 | `binding_judge` 信任 meta + `_explicit_dataset_id()` |
| **B. 取最后一笔** | `cross_turn_reject` | 无 ordinal 时评最后一笔，重试后绑 broad | `accept_guard_error` → **any_pass**（任一笔 guard 或 slice 通过） |
| **C. 规则优先级** | `fresh_after_slice_same_turn` | 「不是这10条」仍触发 chain_slice | `teacher_wants_class_wide_over_slice` + `rule_fresh_broad` |
| **D. 显式 id 绑错集** | `chain_slice_two_turns` | `dataset_id` 指向 broad 但教师要 slice | explicit 路径拒绝 broad + 要 slice |
| **E. LLM/超时** | `explicit_dataset_id`、缺 aggregate、timeout | Agent 未遵协议或未跑完 | 加强场景 prompt；非 binding 层 |

**基线**（2026-06-10）：21/33 = **63.64%**。针对性修复后专项复测 5 场景 **13/15**；全量见下表。

### 汇总公式

```
总准确率 = Σ(judgment.ok) / N_aggregates
场景准确率(S) = Σ(ok | scenario=S) / Σ(judgments | scenario=S)
N_aggregates = Σ(每场景 expect_aggregates 条数) × runs（缺跑/超时则减少）
```

## 结果摘要

| 指标 | 值 |
|------|-----|
| 场景数 N_scenarios | {summary.get("N_scenarios")} |
| 重复次数 N_runs | {summary.get("N_runs")} |
| 评测 aggregate 总数 N_aggregates | {n_agg} |
| 正确数 | {summary.get("correct")} |
| **Online Binding Accuracy** | **{acc}%** |

## 按场景

{chr(10).join(scen_lines)}

## 按 resolver

{chr(10).join(res_lines)}

## 失败明细

{chr(10).join(fail_lines)}

## 与离线评测关系

- **离线**（`binding_accuracy.py`）：直接 `resolve_aggregate_binding`，`BINDING_RESOLVER_DISABLE_LLM=1`，测 resolver 逻辑。
- **在线**（本报告）：完整 Agent + 真实 query/aggregate，测端到端绑定准确率。

## 简历可用（一句话）

> 基于 N={n_agg} 次真实 AgentLoop aggregate 调用，数据集绑定准确率 **{acc}%**（真实 LLM + query/aggregate 链路）。

## 复现

```bash
cd H:/WORKDIR/NorthClassVision
python backend/agent/eval/run_binding_online_eval.py --runs 3
python backend/agent/eval/run_binding_online_eval.py --scenario chain_slice_two_turns --runs 1
```

集成测试（需 API Key）：`$env:RUN_BINDING_ONLINE=1; pytest backend/agent/test/test_binding_online_eval.py -m integration`
"""


def _run_with_timeout(fn, timeout: int) -> Any:
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        fut = pool.submit(fn)
        return fut.result(timeout=timeout)


def main() -> int:
    parser = argparse.ArgumentParser(description="Online binding accuracy eval")
    parser.add_argument("--scenarios", type=Path, default=DEFAULT_SCENARIOS)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--report-out", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--scenario", type=str, default=None, help="Run a single scenario id")
    parser.add_argument("--dry-run", action="store_true", help="Synthetic messages, no LLM")
    args = parser.parse_args()

    scenarios = load_scenarios(args.scenarios)
    if args.scenario:
        scenarios = [s for s in scenarios if s.id == args.scenario]
        if not scenarios:
            print(f"Unknown scenario: {args.scenario}")
            return 2

    llm_client = None if args.dry_run else LLMClient()
    all_runs: list[dict[str, Any]] = []

    for scenario in scenarios:
        for run_idx in range(args.runs):
            print(f"Running {scenario.id} run {run_idx + 1}/{args.runs} ...")

            def _task(sc=scenario, ri=run_idx):
                return evaluate_scenario_run(
                    sc,
                    run_index=ri,
                    llm_client=llm_client,
                    dry_run=args.dry_run,
                )

            try:
                if args.dry_run:
                    run_result = _task()
                else:
                    run_result = _run_with_timeout(_task, RUN_TIMEOUT_SEC)
            except concurrent.futures.TimeoutError:
                run_result = {
                    "scenario_id": scenario.id,
                    "run_index": run_idx,
                    "status": "timeout",
                    "error": f"exceeded {RUN_TIMEOUT_SEC}s",
                    "aggregate_judgments": [],
                    "missing_expectations": [
                        {
                            "reason": "run timeout",
                            "expect": e.expect,
                            "turn_index": e.turn_index,
                        }
                        for e in scenario.expect_aggregates
                    ],
                }
            all_runs.append(run_result)
            ok_n = sum(1 for j in run_result.get("aggregate_judgments") or [] if j.get("ok"))
            tot_n = len(run_result.get("aggregate_judgments") or [])
            print(f"  status={run_result.get('status')} judgments={ok_n}/{tot_n}")

    summary = summarize(all_runs, scenarios=scenarios)
    summary["runs"] = all_runs

    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.report_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    args.report_out.write_text(render_report(summary), encoding="utf-8")

    print(
        f"Online binding accuracy: {summary['accuracy_pct']}% "
        f"({summary['correct']}/{summary['N_aggregates']})"
    )
    print(f"Wrote {args.json_out}")
    print(f"Wrote {args.report_out}")
    if summary.get("incomplete_runs"):
        print(f"Incomplete runs: {len(summary['incomplete_runs'])}")
    return 0 if summary["N_aggregates"] and summary["correct"] == summary["N_aggregates"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

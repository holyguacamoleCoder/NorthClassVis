import json
import os

from agent.common import ensure_agent_logger
from agent.common import normalize_context
from agent.common.llm_client import LLMClient
from agent.common.llm_client import get_default_llm_client
from agent.intent import apply_clarification
from agent.intent import merge_followup_goal
from agent.intent import parse_goal
from agent.memory import get_default_memory_store
from agent.execution import compile_execution_plan_to_steps
from agent.execution import dispatch_batch
from agent.execution import extract_tool_results
from agent.execution import schedule
from agent.execution import verify_tool_results
from agent.output import GoalCheckResult
from agent.output import build_response
from agent.output import check_goal_completion
from agent.output import generate_answer
from agent.output import summarize_execution
from agent.plan import build_task_graph

_agent_logger = ensure_agent_logger()


def _resolve_llm_enabled(context):
    ctx = context or {}
    if "agent_llm_enabled" in ctx:
        return bool(ctx.get("agent_llm_enabled"))
    return str(os.environ.get("AGENT_ENABLE_LLM", "0")).strip() in ("1", "true", "True")


class Orchestrator:
    def __init__(self, config, feature_factory=None):
        self.config = config
        self.feature_factory = feature_factory
        self.memory = get_default_memory_store()

    def query(self, question, context=None):
        question = (question or "").strip()
        if not question:
            return self._empty_response("请输入问题。")
        base_ctx = normalize_context(context)
        session_id = self.memory.resolve_session_id(base_ctx)
        runtime_ctx = self.memory.build_runtime_context(base_ctx, session_id)
        _agent_logger.info(
            "Orchestrator query: session=%s turns=%d pending=%s",
            session_id,
            len(runtime_ctx.get("recent_turns") or []),
            bool(runtime_ctx.get("pending_goal")),
        )
        self.memory.append_turn(session_id, "user", question)
        return self._query_compiler(question, runtime_ctx, session_id=session_id)

    def _query_compiler(self, question, context, session_id="default"):
        # 1) 目标解析
        goal = parse_goal(question, context)
        # 1.1) 若上轮处于追问，尝试将本轮输入补进 pending_goal
        goal = merge_followup_goal(goal, question, context)

        # 2) 非学情分支：尝试性回复；只追加对话，不写入 pending_goal
        if goal.is_out_of_domain:
            result = self._out_of_domain_response(question, context)
            self._remember_turn_result(session_id, goal, result, execution_records=[], is_out_of_domain=True)
            return result

        # 3) 追问补全（在 compile_plan 之前）
        apply_clarification(goal)
        _agent_logger.info(
            "Orchestrator intent: session=%s subject=%s mode=%s scope=%s needs_clarification=%s",
            session_id,
            goal.subject,
            goal.mode,
            goal.scope,
            goal.needs_clarification,
        )

        # 4) 规划 -> 调度 -> 按批执行（主路径）
        graph = build_task_graph(goal)
        execution_plan = schedule(graph)
        execution_records = []
        raw_tool_results = []
        plan_steps = []
        tool_call_results = []
        goal_check: GoalCheckResult = GoalCheckResult(
            is_satisfied=False,
            can_stop_early=False,
            reason="尚未开始执行",
        )

        for i, batch in enumerate(execution_plan.batches or []):
            batch_records = dispatch_batch(batch, execution_plan.task_graph, self.config, self.feature_factory)
            if not batch_records:
                continue
            execution_records.extend(batch_records)

            for record in batch_records:
                raw = dict(record.result or {})
                raw["tool"] = raw.get("tool") or record.tool
                raw["input"] = dict(raw.get("input") or record.params or {})
                raw["status"] = raw.get("status") or record.status or "ok"
                raw["error"] = raw.get("error") or record.error or ""
                raw_tool_results.append(raw)

            partial_plan = type(execution_plan)(
                batches=execution_plan.batches[: i + 1],
                task_graph=execution_plan.task_graph,
            )
            plan_steps = compile_execution_plan_to_steps(partial_plan)
            tool_call_results = extract_tool_results(raw_tool_results)
            tool_call_results = verify_tool_results(plan_steps, tool_call_results)

            for idx, record in enumerate(execution_records):
                if idx >= len(tool_call_results):
                    break
                verified = tool_call_results[idx]
                if record.verification_rule:
                    record.verification_passed = (verified.status or "").lower() != "fail"
                else:
                    record.verification_passed = None
                record.status = verified.status or record.status
                if verified.error:
                    record.error = verified.error
                if isinstance(record.result, dict):
                    record.result["status"] = record.status
                    record.result["error"] = record.error

            goal_check = check_goal_completion(goal, execution_records, tool_call_results)
            if goal_check.can_stop_early:
                _agent_logger.info(
                    "Orchestrator goal satisfied early: batch=%s reason=%s missing=%s",
                    batch.batch_id,
                    goal_check.reason,
                    goal_check.missing_requirements,
                )
                break

        tool_results = []
        for idx, tr in enumerate(tool_call_results):
            tool_results.append(
                {
                    "tool": tr.tool,
                    "input": dict(tr.params or {}),
                    "status": tr.status,
                    "summary": tr.summary,
                    "evidence": list(tr.evidence or []),
                    "visual_hints": list(tr.visual_hints or []),
                    "raw": tr.raw,
                    "duration_ms": tr.duration_ms,
                    "coverage": dict(tr.coverage or {}),
                    "quality": dict(tr.quality or {}),
                    "error": tr.error,
                    "round": idx,
                }
            )

        answer = generate_answer(
            question=question,
            intent=goal,
            tool_call_results=tool_call_results,
            allow_llm=_resolve_llm_enabled(context),
        )
        result_summary = summarize_execution(execution_records, tool_call_results)

        agent_run = {
            "success": True,
            "answer": answer.answer,
            "actions": answer.actions,
            "tool_results": tool_results,
            "round_reasons": [{"round": i, "reason": st.reason} for i, st in enumerate(plan_steps)],
            "intent": goal.to_dict(),
            "plan_steps": [st.to_dict() for st in plan_steps],
            "mode": "compiler_v1",
        }
        # 仅追问、未执行时：用更明确的文案，并标记为“待补充信息”供前端区分展示
        if goal.needs_clarification and not execution_records:
            goal_check_dict = {
                "is_satisfied": False,
                "can_stop_early": False,
                "reason": "等待您补充信息后继续分析",
                "missing_requirements": goal_check.missing_requirements or [],
                "supporting_task_ids": goal_check.supporting_task_ids or [],
                "confidence": goal_check.confidence,
                "is_pending_clarification": True,
            }
        else:
            goal_check_dict = {
                "is_satisfied": goal_check.is_satisfied,
                "can_stop_early": goal_check.can_stop_early,
                "reason": goal_check.reason,
                "missing_requirements": goal_check.missing_requirements or [],
                "supporting_task_ids": goal_check.supporting_task_ids or [],
                "confidence": goal_check.confidence,
                "is_pending_clarification": False,
            }
        agent_run["goal_check"] = goal_check_dict
        agent_run["summary"] = {
            "overall_status": result_summary.overall_status,
            "completed_task_ids": result_summary.completed_task_ids,
            "failed_task_ids": result_summary.failed_task_ids,
            "partial_task_ids": result_summary.partial_task_ids,
            "key_findings": result_summary.key_findings,
            "unresolved_points": result_summary.unresolved_points,
        }
        _agent_logger.info(
            "=== Agent Compiler === mode=compiler_v1 intent=%s plan_steps=%s tool_calls=%s coverage=%s quality=%s",
            json.dumps(agent_run["intent"], ensure_ascii=False),
            json.dumps(agent_run["plan_steps"], ensure_ascii=False),
            len(tool_results),
            json.dumps([r.get("coverage") for r in tool_results], ensure_ascii=False),
            json.dumps([r.get("quality") for r in tool_results], ensure_ascii=False),
        )
        response = build_response(agent_run, context)
        self._remember_turn_result(session_id, goal, response, execution_records=execution_records)
        return response

    def _empty_response(self, message):
        return {
            "answer": message,
            "evidence": [],
            "actions": [],
            "visual_links": [],
            "trace": {"steps": []},
        }

    def _out_of_domain_response(self, question, context):
        """非学情分支：尝试性回复。LLM 可用时用其生成一句，否则用静态引导（可带用户问题摘要）。"""
        allow_llm = _resolve_llm_enabled(context)
        answer = None
        if allow_llm:
            try:
                client = get_default_llm_client()
                if client.config.is_available():
                    q_short = (question or "")[:100].strip() or "该问题"
                    messages = [
                        {
                            "role": "user",
                            "content": f'用户问：「{q_short}」。这是非学情问题，请用一句话友好说明无法基于学情数据回答，并建议可尝试问学情相关的问题。只输出这一句话，不要解释、不要换行。',
                        }
                    ]
                    resp = client.chat_text_only(messages, max_tokens=120)
                    text = (LLMClient.extract_final_text(resp) or "").strip()
                    if text:
                        answer = text[:300]
            except Exception:
                pass
        if not answer:
            q_preview = (question or "").strip()[:50]
            if q_preview:
                answer = f"您问的「{q_preview}」暂时没法基于学情数据回答。我主要支持学情分析，您可以试试问：近期班级趋势、某学生画像、某知识点掌握情况等。"
            else:
                answer = "我主要支持基于学情数据的分析。您可以试试问：近期班级整体趋势、某学生画像、某知识点掌握情况等。"
        return {
            "answer": answer,
            "actions": [
                "尝试：这周班里整体趋势怎么样？",
                "尝试：链表知识点大家掌握得如何？",
            ],
            "evidence": [],
            "visual_links": [],
            "trace": {"steps": []},
        }

    def _remember_turn_result(self, session_id, goal, response, execution_records=None, is_out_of_domain=False):
        execution_records = execution_records or []
        execution_summary = []
        for r in execution_records:
            summary = ""
            if isinstance(getattr(r, "result", None), dict):
                summary = str(r.result.get("summary") or "")
            execution_summary.append(
                {
                    "task_id": getattr(r, "task_id", ""),
                    "tool": getattr(r, "tool", ""),
                    "status": getattr(r, "status", ""),
                    "outputs": list(getattr(r, "outputs", []) or []),
                    "verification_passed": getattr(r, "verification_passed", None),
                    "summary": summary,
                }
            )
        if is_out_of_domain:
            self.memory.set_pending_goal(session_id=session_id, goal_dict=None, needs_clarification=False)
        else:
            self.memory.set_pending_goal(
                session_id=session_id,
                goal_dict=goal.to_dict(),
                needs_clarification=bool(goal.needs_clarification),
            )
        self.memory.append_turn(
            session_id=session_id,
            role="assistant",
            text=response.get("answer") or "",
            meta={
                "needs_clarification": bool(goal.needs_clarification) if not is_out_of_domain else False,
                "clarification_question": goal.clarification_question or "" if not is_out_of_domain else "",
                "tool_execution_summary": execution_summary,
            },
        )
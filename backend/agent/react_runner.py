# 多轮 ReAct 循环：调用 LLM，执行 tool_calls，回填 observation，直到最终回答或达到 max_rounds。
# 入口：run_agent(question, context, config, feature_factory)。当前业务主入口为 Orchestrator.query（compiler_v1）。

import json
import logging

from agent.common import extract_first_json_object
from agent.common import get_react_agent_system_prompt
from agent.common import get_react_planner_instruction
from agent.common import get_react_synthesis_instruction
from agent.common.llm_client import LLMClient
from agent.common.llm_client import get_default_llm_client
from agent.tools import get_openai_tools
from agent.tools.runner import run_tool_calls


MAX_ROUNDS = 5
MAX_TOOL_CALLS_PER_ROUND = 10
_logger = logging.getLogger("agent.llm")


def _to_preview_text(value, limit=800):
    """将任意对象转为日志友好的短文本。"""
    if value is None:
        return ""
    if isinstance(value, str):
        return value[:limit]
    try:
        return json.dumps(value, ensure_ascii=False)[:limit]
    except Exception:
        return str(value)[:limit]


def _agent_system_prompt():
    """Agent 用：可调用工具、多轮决策。"""
    return get_react_agent_system_prompt()


def _user_message(question, context):
    """构造首条 user 消息。"""
    ctx = context or {}
    parts = [f"教师问题：{question}"]
    if ctx.get("classes") or ctx.get("majors") or ctx.get("selected_student_ids"):
        parts.append(f"当前上下文：班级={ctx.get('classes')}，专业={ctx.get('majors')}，已选学生数={len(ctx.get('selected_student_ids') or [])}")
    return "\n\n".join(parts)


def _observation_content(tool_result):
    """将 ToolResult 转为给模型看的 observation 字符串。"""
    s = tool_result.get("summary") or ""
    raw = tool_result.get("raw")
    if raw is not None:
        try:
            snippet = json.dumps(raw, ensure_ascii=False)[:800]
            s = s + "\n" + snippet if s else snippet
        except Exception:
            pass
    return s or "(无返回)"


def _parse_final_answer(text):
    """从最终文本中解析 answer 与 actions。"""
    if not text or not text.strip():
        return None, []
    text = text.strip()
    if "{" in text and "}" in text:
        start = text.index("{")
        end = text.rindex("}") + 1
        try:
            obj = json.loads(text[start:end])
            return obj.get("answer"), obj.get("actions") or []
        except Exception:
            pass
    return text[:500], []


class ReActAgent:
    """封装 ReAct 多轮循环与会话状态。"""

    def __init__(
        self,
        config,
        feature_factory=None,
        max_rounds=MAX_ROUNDS,
        max_tool_calls_per_round=MAX_TOOL_CALLS_PER_ROUND,
        llm_client=None,
    ):
        self.config = config
        self.feature_factory = feature_factory
        self.max_rounds = max_rounds
        self.max_tool_calls_per_round = max_tool_calls_per_round
        self._llm_client = llm_client  # 可注入，便于单测或换模型

        self.messages = []
        self.tool_results = []
        self.round_reasons = []
        self.final_text = ""
        self.question = ""
        self.context = {}

    def run(self, question, context=None):
        """
        执行 ReAct 循环，返回 dict：
        - success: bool，是否得到最终回答
        - final_text: str，最后一轮模型文本
        - answer: str
        - actions: list[str]
        - tool_results: list[ToolResult]，所有轮次工具结果
        - messages: 最终 messages（仅供调试）
        - round_reasons: list[dict]，按轮记录的 reason 文本
        """
        self._reset(question, context)
        tools_payload = get_openai_tools()

        for round_idx in range(self.max_rounds):
            plan = self._plan_round(round_idx, tools_payload)
            if not plan:
                return self._failure_result()
            reason_text = plan.get("reason") or f"第 {round_idx + 1} 轮：继续收集证据。"
            self.round_reasons.append({"round": round_idx, "reason": reason_text})
            _logger.info("=== ReAct Round %s Reason === %s", round_idx, _to_preview_text(reason_text))

            decision = plan.get("decision")
            tool_plan = plan.get("tool_plan") or []
            if decision == "call_tool" and tool_plan:
                self._execute_tool_plan(round_idx, tool_plan)
                continue
            _logger.info("=== ReAct Round %s 决策 === finish", round_idx)
            break

        self.final_text = self._synthesize_final_answer()
        if not self.final_text:
            self.final_text = "当前数据不足以支持该结论。"
        answer, actions = _parse_final_answer(self.final_text)
        _logger.info(
            "=== ReAct 汇总 === rounds=%s, tool_results=%s\nfinal_text (前800字): %s\nparsed_answer: %s\nactions: %s",
            len(self.round_reasons),
            len(self.tool_results),
            _to_preview_text(self.final_text),
            _to_preview_text(answer, limit=400),
            _to_preview_text(actions, limit=400),
        )
        return {
            "success": True,
            "final_text": self.final_text,
            "answer": answer,
            "actions": actions,
            "tool_results": self.tool_results,
            "messages": self.messages,
            "round_reasons": self.round_reasons,
        }

    def _reset(self, question, context):
        self.question = (question or "").strip()
        self.context = context or {}
        self.messages = [
            {"role": "system", "content": _agent_system_prompt()},
            {"role": "user", "content": _user_message(self.question, self.context)},
        ]
        self.tool_results = []
        self.round_reasons = []
        self.final_text = ""

    def _failure_result(self):
        _logger.warning(
            "=== ReAct 失败 === messages=%s, collected_tool_results=%s",
            len(self.messages),
            len(self.tool_results),
        )
        return {
            "success": False,
            "final_text": "",
            "answer": None,
            "actions": [],
            "tool_results": self.tool_results,
            "messages": self.messages,
            "round_reasons": self.round_reasons,
        }

    def _plan_round(self, round_idx, tools_payload):
        """Reason-only 规划：禁止 tool 调用，只输出计划 JSON。"""
        available_tools = []
        for t in tools_payload or []:
            fn = (t.get("function") or {})
            available_tools.append({
                "name": fn.get("name"),
                "description": fn.get("description", ""),
                "parameters": fn.get("parameters", {}),
            })
        instruction = get_react_planner_instruction(
            question=self.question,
            context=self.context,
            available_tools=available_tools,
            max_tool_calls=self.max_tool_calls_per_round,
        )
        planner_messages = list(self.messages)
        planner_messages.append({"role": "user", "content": instruction})
        _logger.info("=== ReAct Round %s 阶段 === reason/planning", round_idx)
        client = getattr(self, "_llm_client", None) or get_default_llm_client()
        resp = client.chat_text_only(planner_messages)
        if not resp:
            return None
        plan_text = LLMClient.extract_final_text(resp)
        plan_obj = extract_first_json_object(plan_text) or {}
        reason = (plan_obj.get("reason") or "").strip()
        decision = (plan_obj.get("decision") or "").strip().lower()
        if decision not in ("call_tool", "finish"):
            decision = "call_tool"
        tool_plan = self._sanitize_tool_plan(plan_obj.get("tool_plan") or [], tools_payload)
        if decision == "call_tool" and not tool_plan:
            # 无有效工具时强制收敛为 finish，避免空转
            decision = "finish"
        return {"reason": reason, "decision": decision, "tool_plan": tool_plan}

    def _sanitize_tool_plan(self, tool_plan, tools_payload):
        allowed_names = set()
        for t in tools_payload or []:
            fn = (t.get("function") or {})
            if fn.get("name"):
                allowed_names.add(fn["name"])
        safe_plan = []
        for item in tool_plan:
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            if name not in allowed_names:
                continue
            args = item.get("arguments")
            if not isinstance(args, dict):
                args = {}
            safe_plan.append({"name": name, "arguments": args})
            if len(safe_plan) >= self.max_tool_calls_per_round:
                break
        return safe_plan

    def _execute_tool_plan(self, round_idx, tool_plan):
        _logger.info("=== ReAct Round %s 阶段 === act/tool_execution", round_idx)
        tool_calls_for_api = []
        for idx, item in enumerate(tool_plan):
            tool_calls_for_api.append({
                "id": f"plan-{round_idx}-{idx}",
                "type": "function",
                "function": {"name": item["name"], "arguments": json.dumps(item["arguments"], ensure_ascii=False)},
            })
        # 该 assistant 消息由后端计划驱动，明确记录当前要执行的 act。
        self.messages.append({"role": "assistant", "content": None, "tool_calls": tool_calls_for_api})
        _logger.info("=== ReAct Round %s Tool Invokes === %s", round_idx, _to_preview_text(tool_plan))
        results = run_tool_calls(tool_plan, self.config, self.feature_factory, round_=round_idx)
        self.tool_results.extend(results)
        _logger.info(
            "=== ReAct Round %s Observations === %s",
            round_idx,
            _to_preview_text([{"tool": r.get("tool"), "summary": r.get("summary"), "status": r.get("status")} for r in results]),
        )
        for i, item in enumerate(tool_plan):
            content = _observation_content(results[i]) if i < len(results) else "(执行失败)"
            self.messages.append({"role": "tool", "tool_call_id": f"plan-{round_idx}-{i}", "content": content})

    def _synthesize_final_answer(self):
        """synthesize 阶段：基于 observation 输出最终 answer/actions JSON。"""
        instruction = get_react_synthesis_instruction()
        synth_messages = list(self.messages)
        synth_messages.append({"role": "user", "content": instruction})
        _logger.info("=== ReAct 阶段 === synthesize/final_answer")
        client = getattr(self, "_llm_client", None) or get_default_llm_client()
        resp = client.chat_text_only(synth_messages)
        if not resp:
            return ""
        text = LLMClient.extract_final_text(resp)
        # 记录最终 assistant 消息，保证 messages 完整
        self.messages.append({"role": "assistant", "content": text or None})
        return text or ""


def run_agent(question, context, config, feature_factory=None):
    """兼容入口：委托给 ReActAgent。"""
    return ReActAgent(config=config, feature_factory=feature_factory).run(question, context)

from agent.common import AnswerContract
from agent.common import ensure_agent_logger
from agent.common import extract_first_json_object
from agent.common import get_compiler_answer_system_prompt
from agent.common import get_default_llm_client
import json

_agent_logger = ensure_agent_logger()


def _build_template_answer(question, intent, tool_call_results):
    if intent.needs_clarification:
        return AnswerContract(
            answer=intent.clarification_question,
            actions=["补充 student_ids 后我可以继续分析。"],
        )
    if not tool_call_results:
        return AnswerContract(
            answer="当前数据不足以支持该结论。",
            actions=["请补充筛选范围或换一个更具体的问题。"],
        )

    summaries = [r.summary for r in tool_call_results if r.summary]
    not_covered = [r for r in tool_call_results if not (r.coverage or {}).get("covered", False)]
    if not_covered:
        reasons = [((r.coverage or {}).get("reason") or "样本不足") for r in not_covered][:2]
        answer = "当前数据不足以支持该结论。缺失维度：" + "；".join(reasons)
    else:
        answer = "；".join(summaries[:2]) or "根据当前数据已完成分析。"
    actions = _build_adaptive_actions(tool_call_results)
    return AnswerContract(answer=answer, actions=actions)


def _build_adaptive_actions(tool_call_results):
    actions = []
    tools = [str((r.tool or "")).strip() for r in (tool_call_results or [])]
    has_week = any(t in ("query_class", "query_weekly_trend") for t in tools)
    has_question = any(t == "query_question" for t in tools)
    has_student = any(t == "query_student" for t in tools)

    if has_week:
        actions.append("可在周趋势图查看知识点变化与风险学生。")
    if has_question:
        actions.append("如需题目级结论，请补充 title_id 后继续分析。")
    if has_student:
        actions.append("可继续追问该学生的薄弱知识点和提升建议。")
    actions.append("可在运行轨迹中查看能力调用与覆盖度。")
    return actions[:3]


def _build_llm_messages(question, intent, tool_call_results):
    payload = {
        "question": question,
        "intent": intent.to_dict(),
        "results": [r.to_dict() for r in tool_call_results],
        "output_schema": {"answer": "string", "actions": ["string"]},
    }
    system = get_compiler_answer_system_prompt()
    user = json.dumps(payload, ensure_ascii=False)
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


class AnswerGenerator:
    """将工具调用结果（及可选 LLM 输出）规范为 AnswerContract，支持注入 llm_client。"""

    def __init__(self, llm_client_instance=None):
        self._llm_client = llm_client_instance

    def _client(self):
        return self._llm_client or get_default_llm_client()

    def generate_answer(self, question, intent, tool_call_results, allow_llm=True):
        template = _build_template_answer(question, intent, tool_call_results)
        _agent_logger.info(
            "Answer generate: allow_llm=%s tool_results=%d",
            bool(allow_llm),
            len(tool_call_results or []),
        )
        if not allow_llm:
            _agent_logger.info("Answer generate: fallback=template reason=llm_disabled")
            return template

        try:
            text = self._client().chat_text_only_content(
                _build_llm_messages(question, intent, tool_call_results),
                max_tokens=400,
            )
        except Exception as e:
            _agent_logger.warning("Answer generate: fallback=template reason=llm_exception err=%s", e)
            return template
        _agent_logger.debug("Answer generate: llm_text_len=%d", len(text or ""))
        obj = extract_first_json_object(text)
        if not obj:
            _agent_logger.info("Answer generate: fallback=template reason=json_parse_failed")
            return template
        answer = obj.get("answer") if isinstance(obj.get("answer"), str) else template.answer
        actions = obj.get("actions") if isinstance(obj.get("actions"), list) else _build_adaptive_actions(tool_call_results)
        if not isinstance(obj.get("actions"), list):
            _agent_logger.info("Answer generate: actions_fallback=adaptive reason=invalid_actions")
        return AnswerContract(answer=answer, actions=actions)


_default_generator = None


def generate_answer(question, intent, tool_call_results, allow_llm=True, llm_client_instance=None):
    """将问题、意图、工具调用结果规范为 AnswerContract；可选 LLM 润色。"""
    global _default_generator
    if _default_generator is None:
        _default_generator = AnswerGenerator()
    gen = AnswerGenerator(llm_client_instance=llm_client_instance) if llm_client_instance else _default_generator
    return gen.generate_answer(question, intent, tool_call_results, allow_llm=allow_llm)

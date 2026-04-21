from agent.common.contracts import ToolResult
from agent.intent.schemas import GoalSpec
from agent.output.answer_generator import generate_answer


class _FakeLLM:
    def __init__(self, text):
        self._text = text

    def chat_text_only_content(self, messages, max_tokens=400):
        return self._text


def test_answer_generator_template_actions_are_adaptive_when_llm_disabled():
    goal = GoalSpec(subject=["class"], mode=["trend"])
    tr = ToolResult(tool="query_class", params={"mode": "trend"}, status="ok", summary="班级趋势")
    out = generate_answer(
        "班级趋势如何",
        goal,
        [tr],
        allow_llm=False,
    )
    assert out.answer
    assert any("周趋势图" in a for a in out.actions)


def test_answer_generator_fallback_actions_when_llm_actions_invalid():
    goal = GoalSpec(subject=["question"], mode=["detail"])
    tr = ToolResult(tool="query_question", params={"mode": "detail"}, status="ok", summary="题目明细")
    out = generate_answer(
        "题目明细",
        goal,
        [tr],
        allow_llm=True,
        llm_client_instance=_FakeLLM('{"answer":"已完成分析","actions":"not_list"}'),
    )
    assert out.answer == "已完成分析"
    assert isinstance(out.actions, list)
    assert any("title_id" in a or "题目级" in a for a in out.actions)


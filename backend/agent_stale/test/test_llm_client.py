"""LLMClient 兼容性测试：文本便捷接口与 tool 链路应可共存。"""

from types import SimpleNamespace

from agent.common.llm_client import LLMClient
from agent.common.llm_client import LLMConfig


class _FakeCompletions:
    def __init__(self, response):
        self._response = response
        self.last_kwargs = None

    def create(self, **kwargs):
        self.last_kwargs = kwargs
        return self._response


class _FakeOpenAIClient:
    def __init__(self, response):
        self.chat = SimpleNamespace(completions=_FakeCompletions(response))


def _build_response(content="", tool_calls=None, finish_reason="stop"):
    message = SimpleNamespace(content=content, tool_calls=tool_calls or [])
    choice = SimpleNamespace(message=message, finish_reason=finish_reason)
    return SimpleNamespace(choices=[choice])


def test_chat_text_only_content_returns_text_without_breaking_raw_mode():
    client = LLMClient(config=LLMConfig(api_key="x", base_url="http://x", model="m"))
    response = _build_response(content="  hello world  ")
    fake_openai = _FakeOpenAIClient(response)
    client.set_client(fake_openai)

    text = client.chat_text_only_content([{"role": "user", "content": "hi"}], max_tokens=128)
    assert text == "hello world"
    assert fake_openai.chat.completions.last_kwargs["max_tokens"] == 128


def test_chat_with_tools_still_returns_raw_response_for_tool_calls():
    client = LLMClient(config=LLMConfig(api_key="x", base_url="http://x", model="m"))
    tool_call = SimpleNamespace(
        id="call_1",
        function=SimpleNamespace(name="query_weekly_trend", arguments='{"window":"recent_2w"}'),
    )
    response = _build_response(content="", tool_calls=[tool_call])
    fake_openai = _FakeOpenAIClient(response)
    client.set_client(fake_openai)

    raw = client.chat_with_tools(
        [{"role": "user", "content": "最近趋势"}],
        tools=[{"type": "function", "function": {"name": "query_weekly_trend"}}],
        parallel_tool_calls=True,
        max_tokens=256,
    )
    calls = LLMClient.extract_tool_calls(raw)
    assert len(calls) == 1
    assert calls[0]["name"] == "query_weekly_trend"
    assert "window" in calls[0]["arguments"]

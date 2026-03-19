# 封装 OpenAI 兼容 SDK：面向类的 LLM 配置与调用，统一 chat 入口。

import logging
import os
from typing import Any, Dict, List, Optional

_logger = logging.getLogger("agent.llm")


class LLMConfig:
    """LLM 连接与模型配置，可从环境变量加载。"""

    def __init__(self, api_key="", base_url="https://api.openai.com/v1", model="gpt-3.5-turbo"):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/") if base_url else "https://api.openai.com/v1"
        self.model = model or "gpt-3.5-turbo"

    @classmethod
    def from_env(cls):
        api_key = (os.environ.get("OPENAI_API_KEY") or "").strip()
        base_url = (os.environ.get("OPENAI_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
        model = os.environ.get("OPENAI_MODEL") or "gpt-3.5-turbo"
        return cls(api_key=api_key, base_url=base_url, model=model)

    def is_available(self):
        return bool(self.api_key)


class LLMClient:
    """
    统一 LLM 调用入口：文本对话与带工具的对话分离，避免业务层重复传 tools/parallel_tool_calls。
    """

    def __init__(self, config=None):
        self._config = config or LLMConfig.from_env()
        self._client: Any = None

    @property
    def config(self) -> LLMConfig:
        return self._config

    def get_client(self):
        if self._client is not None:
            return self._client
        if not self._config.is_available():
            return None
        try:
            from openai import OpenAI
            self._client = OpenAI(
                api_key=self._config.api_key,
                base_url=self._config.base_url,
            )
            return self._client
        except Exception:
            return None

    def set_client(self, client: Any) -> None:
        self._client = client

    def chat_text_only(
        self,
        messages: List[Dict[str, Any]],
        max_tokens: int = 1024,
    ) -> Optional[Any]:
        return self._create_completion(
            messages=messages,
            tools=None,
            parallel_tool_calls=False,
            max_tokens=max_tokens,
        )

    def chat_text_only_content(
        self,
        messages: List[Dict[str, Any]],
        max_tokens: int = 1024,
    ) -> str:
        """
        便捷接口：文本对话直接返回最终文本内容。
        保留 chat_text_only 的 raw response 语义，避免影响 tool 调用链路。
        """
        resp = self.chat_text_only(messages=messages, max_tokens=max_tokens)
        return self.extract_final_text(resp)

    def chat_with_tools(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        parallel_tool_calls: bool = True,
        max_tokens: int = 1024,
    ) -> Optional[Any]:
        return self._create_completion(
            messages=messages,
            tools=tools,
            parallel_tool_calls=parallel_tool_calls,
            max_tokens=max_tokens,
        )

    def _create_completion(
        self,
        messages,
        tools=None,
        parallel_tool_calls: bool = True,
        max_tokens: int = 1024,
    ) -> Optional[Any]:
        client = self.get_client()
        if not client:
            return None
        try:
            user_preview = ""
            for m in reversed(messages or []):
                if m.get("role") == "user":
                    content = m.get("content") or ""
                    if isinstance(content, str):
                        user_preview = content[:500]
                    break
            _logger.info(
                "=== LLM 请求 === messages=%s, tools=%s\nuser_content (前500字): %s",
                len(messages or []),
                len(tools) if tools else 0,
                user_preview,
            )
            request_kwargs = {
                "model": self._config.model,
                "messages": messages,
                "max_tokens": max_tokens,
            }
            if tools:
                request_kwargs["tools"] = tools
                request_kwargs["tool_choice"] = "auto"
                request_kwargs["parallel_tool_calls"] = parallel_tool_calls
            resp = client.chat.completions.create(**request_kwargs)
            if resp and resp.choices:
                msg = resp.choices[0].message
                content = getattr(msg, "content", None) or ""
                tool_calls = getattr(msg, "tool_calls", None) or []
                content_preview = (content if isinstance(content, str) else str(content))[:800]
                if tool_calls:
                    names = [
                        (t.function.name if hasattr(t, "function") and hasattr(t.function, "name") else getattr(t, "name", ""))
                        for t in tool_calls
                    ]
                    _logger.info(
                        "=== LLM 返回 === tool_calls=%s 个: %s\nassistant_content (前800字): %s",
                        len(tool_calls),
                        names,
                        content_preview,
                    )
                else:
                    _logger.info("=== LLM 返回 ===\n%s", content_preview[:2000])
            return resp
        except Exception as e:
            _logger.exception("ReAct LLM 调用异常: %s", e)
            return None

    @staticmethod
    def extract_tool_calls(response: Any) -> List[Dict[str, Any]]:
        if not response or not response.choices:
            return []
        msg = response.choices[0].message
        if not getattr(msg, "tool_calls", None):
            return []
        return [
            {
                "id": tc.id,
                "name": tc.function.name if hasattr(tc, "function") else getattr(tc, "name", ""),
                "arguments": tc.function.arguments if hasattr(tc, "function") and tc.function.arguments else getattr(tc, "arguments", "{}"),
            }
            for tc in msg.tool_calls
        ]

    @staticmethod
    def extract_final_text(response: Any) -> str:
        if not response or not response.choices:
            return ""
        msg = response.choices[0].message
        content = getattr(msg, "content", None) or ""
        if isinstance(content, str):
            return content.strip()
        return ""


_default_client = None


def get_default_llm_client():
    global _default_client
    if _default_client is None:
        _default_client = LLMClient()
    return _default_client


def get_client():
    return get_default_llm_client().get_client()


def get_model():
    return get_default_llm_client().config.model


def create_completion(messages, tools=None, parallel_tool_calls=True, max_tokens=1024):
    cl = get_default_llm_client()
    if tools:
        return cl.chat_with_tools(messages, tools, parallel_tool_calls=parallel_tool_calls, max_tokens=max_tokens)
    return cl.chat_text_only(messages, max_tokens=max_tokens)


def extract_tool_calls(response):
    return LLMClient.extract_tool_calls(response)


def extract_final_text(response):
    return LLMClient.extract_final_text(response)

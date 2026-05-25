# 封装 OpenAI 兼容 SDK：面向类的 LLM 配置与调用，统一 chat 入口。

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from dotenv import load_dotenv
except Exception:
    load_dotenv = None

if load_dotenv:
    BACKEND_DIR = Path(__file__).resolve().parents[2]
    load_dotenv(dotenv_path=BACKEND_DIR / ".env", override=False)

from common.logger import get_logger, log_event, truncate_for_log

_llm_log = get_logger("llm")


class LLMCallError(Exception):
    """Raised when an LLM API call fails; carries optional recovery classification."""

    def __init__(
        self,
        message: str,
        *,
        cause: BaseException | None = None,
        recovery_action: "RecoveryActionLike | None" = None,
    ):
        super().__init__(message)
        self.cause = cause
        self.recovery_action = recovery_action or _classify_for_llm_error(cause or self)


# Avoid circular import at runtime; recovery.classify is the source of truth.
RecoveryActionLike = Any


def _classify_for_llm_error(exc: BaseException):
    try:
        from recovery.classify import RecoveryAction, classify_exception

        return classify_exception(exc)
    except Exception:
        from enum import Enum

        class _Fallback(str, Enum):
            FATAL = "fatal"

        return _Fallback.FATAL


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
    统一 LLM 调用入口
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

    def chat_text(
        self,
        system_prompt: Optional[str],
        messages: List[Dict[str, Any]],
        max_tokens: int = 1024,
    ) -> Optional[Any]:
        # 返回文本内容
        resp = self.create_completion(
            system_prompt=system_prompt,
            messages=messages,
            tools=None,
            parallel_tool_calls=False,
            max_tokens=max_tokens,
        )
        return self.extract_final_text(resp)

    def chat_with_tools(
        self,
        system_prompt: Optional[str],
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        parallel_tool_calls: bool = True,
        max_tokens: int = 1024,
    ) -> Optional[Any]:
        # 返回处理过的工具调用
        resp = self.create_completion(
            system_prompt=system_prompt,
            messages=messages,
            tools=tools,
            parallel_tool_calls=parallel_tool_calls,
            max_tokens=max_tokens,
        )
        return self.extract_tool_calls(resp)

    def create_completion(
        self,
        system_prompt: Optional[str],
        messages: List[Dict[str, Any]],
        tools=None,
        parallel_tool_calls: bool = True,
        max_tokens: int = 1024,
        on_content_delta: Optional[Any] = None,
    ) -> Optional[Any]:
        # 返回raw响应
        client = self.get_client()
        if not client:
            raise LLMCallError("LLM client not configured (missing API key or SDK)")
        try:
            request_messages = list(messages or [])
            if system_prompt:
                has_system_message = any(m.get("role") == "system" for m in request_messages if isinstance(m, dict))
                if not has_system_message:
                    request_messages = [
                        {
                            "role": "system",
                            "content": system_prompt,
                        },
                        *request_messages,
                    ]
            user_preview = ""
            for m in reversed(request_messages):
                if m.get("role") == "user":
                    content = m.get("content") or ""
                    if isinstance(content, str):
                        user_preview = content[:500]
                    break
            log_event(
                _llm_log,
                logging.DEBUG,
                "llm_request",
                model=self._config.model,
                messages_count=len(request_messages),
                tools_count=len(tools) if tools else 0,
                user_preview=truncate_for_log(user_preview),
                stream=bool(on_content_delta),
            )
            request_kwargs = {
                "model": self._config.model,
                "messages": request_messages,
                "max_tokens": max_tokens,
            }
            if tools:
                request_kwargs["tools"] = tools
                request_kwargs["tool_choice"] = "auto"
                request_kwargs["parallel_tool_calls"] = parallel_tool_calls
            if on_content_delta:
                request_kwargs["stream"] = True
                return self._create_completion_stream(client, request_kwargs, on_content_delta)
            resp = client.chat.completions.create(**request_kwargs)

            if resp and resp.choices:
                msg = resp.choices[0].message
                content = getattr(msg, "content", None) or ""
                tool_calls = getattr(msg, "tool_calls", None) or []
                content_raw = content if isinstance(content, str) else str(content)
                if tool_calls:
                    names = [
                        (t.function.name if hasattr(t, "function") and hasattr(t.function, "name") else getattr(t, "name", ""))
                        for t in tool_calls
                    ]
                    log_event(
                        _llm_log,
                        logging.DEBUG,
                        "llm_response",
                        tool_calls_count=len(tool_calls),
                        tool_names=names,
                        assistant_preview=truncate_for_log(content_raw, max_len=800),
                    )
                else:
                    log_event(
                        _llm_log,
                        logging.DEBUG,
                        "llm_response",
                        assistant_preview=truncate_for_log(content_raw, max_len=2000),
                    )
            return resp
        except Exception as e:
            log_event(_llm_log, logging.ERROR, "llm_error", error=str(e))
            raise LLMCallError(str(e), cause=e) from e

    def _create_completion_stream(self, client, request_kwargs, on_content_delta):
        stream = client.chat.completions.create(**request_kwargs)
        content_parts: list[str] = []
        tool_calls_acc: dict[int, dict[str, str]] = {}
        finish_reason = None

        for chunk in stream:
            if not chunk.choices:
                continue
            choice = chunk.choices[0]
            if choice.finish_reason:
                finish_reason = choice.finish_reason
            delta = choice.delta
            if not delta:
                continue
            if delta.content:
                content_parts.append(delta.content)
                on_content_delta(delta.content)
            if delta.tool_calls:
                for tc in delta.tool_calls:
                    idx = tc.index
                    acc = tool_calls_acc.setdefault(
                        idx,
                        {"id": "", "name": "", "arguments": ""},
                    )
                    if tc.id:
                        acc["id"] = tc.id
                    if tc.function:
                        if tc.function.name:
                            acc["name"] += tc.function.name
                        if tc.function.arguments:
                            acc["arguments"] += tc.function.arguments

        return self._build_streamed_response(
            content="".join(content_parts),
            tool_calls_acc=tool_calls_acc,
            finish_reason=finish_reason,
        )

    @staticmethod
    def _build_streamed_response(*, content: str, tool_calls_acc: dict, finish_reason):
        class _Fn:
            def __init__(self, name, arguments):
                self.name = name
                self.arguments = arguments

        class _ToolCall:
            def __init__(self, call_id, name, arguments):
                self.id = call_id
                self.function = _Fn(name, arguments)

        class _Message:
            def __init__(self, content, tool_calls):
                self.content = content or None
                self.tool_calls = tool_calls or None

        class _Choice:
            def __init__(self, message, finish_reason):
                self.message = message
                self.finish_reason = finish_reason

        class _Response:
            def __init__(self, choices):
                self.choices = choices

        tool_calls = None
        if tool_calls_acc:
            ordered = [tool_calls_acc[i] for i in sorted(tool_calls_acc)]
            tool_calls = [
                _ToolCall(acc["id"], acc["name"], acc["arguments"])
                for acc in ordered
                if acc.get("name")
            ]
            if not tool_calls:
                tool_calls = None
            elif finish_reason is None:
                finish_reason = "tool_calls"

        message = _Message(content, tool_calls)
        if tool_calls and finish_reason != "tool_calls":
            finish_reason = "tool_calls"
        if not tool_calls and finish_reason is None:
            finish_reason = "stop"
        return _Response([_Choice(message, finish_reason)])

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

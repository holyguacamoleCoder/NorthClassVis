import logging
from dataclasses import dataclass
from typing import Any, Callable

from common.llm_client import LLMCallError, LLMClient
from common.message import coerce_tool_calls_for_api
from common.logger import get_logger, log_event

from .backoff import sleep_backoff
from .classify import RecoveryAction, classify_exception, is_output_truncated
from .config import DEFAULT_RECOVERY_CONFIG, RecoveryConfig

_log = get_logger("recovery")


@dataclass
class RecoveryState:
    max_output_recovery_count: int = 0


def _append_assistant_from_response(messages: list, response: Any) -> None:
    choice = response.choices[0]
    msg = choice.message
    assistant_message: dict[str, Any] = {
        "role": "assistant",
        "content": getattr(msg, "content", None) or "",
    }
    if getattr(msg, "tool_calls", None):
        assistant_message["tool_calls"] = coerce_tool_calls_for_api(msg.tool_calls)
    messages.append(assistant_message)


class RecoveryHandler:
    """Orchestrates max-output continuation, context compact, and transport backoff."""

    def __init__(
        self,
        llm_client: LLMClient,
        *,
        config: RecoveryConfig = DEFAULT_RECOVERY_CONFIG,
        state: RecoveryState | None = None,
    ):
        self.llm_client = llm_client
        self.config = config
        self.state = state or RecoveryState()
        self._last_failure_reason: str | None = None

    def request_completion(
        self,
        *,
        system_prompt: str,
        messages: list,
        tools: list | None,
        max_tokens: int,
        normalize_fn: Callable[[list], list],
        compact_fn: Callable[[], None],
        on_content_delta: Callable[[str], None] | None = None,
    ) -> tuple[Any | None, str | None]:
        """
        Call the LLM with recovery strategies.

        Returns (raw_response, failure_reason). failure_reason is set only on failure.
        May mutate ``messages`` (compact, truncated assistant, continuation user).
        """
        if not self.config.enabled:
            try:
                response = self.llm_client.create_completion(
                    system_prompt=system_prompt,
                    messages=normalize_fn(messages),
                    tools=tools,
                    max_tokens=max_tokens,
                    on_content_delta=on_content_delta,
                )
            except LLMCallError as exc:
                return None, _failure_reason(exc)
            if not response or not getattr(response, "choices", None):
                return None, "llm_no_response"
            return response, None

        while True:
            response = self._call_with_transport_recovery(
                system_prompt=system_prompt,
                messages=messages,
                tools=tools,
                max_tokens=max_tokens,
                normalize_fn=normalize_fn,
                compact_fn=compact_fn,
                on_content_delta=on_content_delta,
            )
            if response is None:
                return None, self._last_failure_reason or "llm_no_response"

            choice = response.choices[0]
            finish_reason = getattr(choice, "finish_reason", None)

            if not is_output_truncated(finish_reason):
                self.state.max_output_recovery_count = 0
                return response, None

            self.state.max_output_recovery_count += 1
            if self.state.max_output_recovery_count > self.config.max_attempts:
                log_event(
                    _log,
                    logging.WARNING,
                    "recovery_max_output_exhausted",
                    attempts=self.config.max_attempts,
                )
                _append_assistant_from_response(messages, response)
                return None, "output_truncated_exhausted"

            log_event(
                _log,
                logging.INFO,
                "recovery_max_output",
                attempt=self.state.max_output_recovery_count,
                max_attempts=self.config.max_attempts,
                finish_reason=finish_reason,
            )
            _append_assistant_from_response(messages, response)
            messages.append(
                {"role": "user", "content": self.config.continuation_message}
            )

    def _call_with_transport_recovery(
        self,
        *,
        system_prompt: str,
        messages: list,
        tools: list | None,
        max_tokens: int,
        normalize_fn: Callable[[list], list],
        compact_fn: Callable[[], None],
        on_content_delta: Callable[[str], None] | None = None,
    ) -> Any | None:
        self._last_failure_reason = None
        max_attempts = self.config.max_attempts

        for attempt in range(max_attempts + 1):
            try:
                response = self.llm_client.create_completion(
                    system_prompt=system_prompt,
                    messages=normalize_fn(messages),
                    tools=tools,
                    max_tokens=max_tokens,
                    on_content_delta=on_content_delta,
                )
            except LLMCallError as exc:
                action = classify_exception(exc)
                reason = _failure_reason(exc)
                if action == RecoveryAction.COMPACT and attempt < max_attempts:
                    log_event(
                        _log,
                        logging.INFO,
                        "recovery_compact",
                        attempt=attempt + 1,
                        error=str(exc)[:200],
                    )
                    compact_fn()
                    continue
                if action == RecoveryAction.BACKOFF and attempt < max_attempts:
                    delay = sleep_backoff(attempt, config=self.config)
                    log_event(
                        _log,
                        logging.INFO,
                        "recovery_backoff",
                        attempt=attempt + 1,
                        delay_s=round(delay, 2),
                        error=str(exc)[:200],
                    )
                    continue
                self._last_failure_reason = reason
                log_event(
                    _log,
                    logging.WARNING,
                    "recovery_api_exhausted",
                    reason=reason,
                    attempts=max_attempts,
                )
                return None

            if response and getattr(response, "choices", None):
                return response

            self._last_failure_reason = "llm_no_response"
            if attempt < max_attempts:
                delay = sleep_backoff(attempt, config=self.config)
                log_event(
                    _log,
                    logging.INFO,
                    "recovery_empty_response",
                    attempt=attempt + 1,
                    delay_s=round(delay, 2),
                )
                continue
            return None

        return None


def _failure_reason(exc: LLMCallError) -> str:
    action = classify_exception(exc)
    if action == RecoveryAction.COMPACT:
        return "context_overflow_exhausted"
    if action == RecoveryAction.BACKOFF:
        return "transient_error_exhausted"
    return "llm_error"

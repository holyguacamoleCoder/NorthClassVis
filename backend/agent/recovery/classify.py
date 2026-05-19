from enum import Enum

from common.llm_client import LLMCallError


class RecoveryAction(str, Enum):
    NONE = "none"
    COMPACT = "compact"
    BACKOFF = "backoff"
    FATAL = "fatal"


_CONTEXT_OVERFLOW_MARKERS = (
    "context_length_exceeded",
    "maximum context",
    "prompt is too long",
    "overlong_prompt",
    "overlong",
    "too many tokens",
    "token limit",
    "max_tokens",
    "context window",
    "reduce the length",
    "input is too long",
    "request too large",
)

_TRANSIENT_MARKERS = (
    "rate limit",
    "ratelimit",
    "too many requests",
    "timeout",
    "timed out",
    "connection",
    "temporarily unavailable",
    "service unavailable",
    "bad gateway",
    "gateway timeout",
)


def _text_blob(exc: BaseException) -> str:
    parts = [str(exc).lower()]
    cause = getattr(exc, "__cause__", None)
    if cause is not None:
        parts.append(str(cause).lower())
    return " ".join(parts)


def is_context_overflow_error(exc: BaseException) -> bool:
    text = _text_blob(exc)
    if any(marker in text for marker in _CONTEXT_OVERFLOW_MARKERS):
        return True
    if "prompt" in text and "long" in text:
        return True
    return False


def is_transient_error(exc: BaseException) -> bool:
    if isinstance(exc, (ConnectionError, TimeoutError, OSError)):
        return True
    status = getattr(exc, "status_code", None)
    if status in (408, 429, 500, 502, 503, 504):
        return True
    text = _text_blob(exc)
    return any(marker in text for marker in _TRANSIENT_MARKERS)


def classify_exception(exc: BaseException) -> RecoveryAction:
    if isinstance(exc, LLMCallError) and exc.recovery_action is not RecoveryAction.NONE:
        return exc.recovery_action
    if is_context_overflow_error(exc):
        return RecoveryAction.COMPACT
    if is_transient_error(exc):
        return RecoveryAction.BACKOFF
    return RecoveryAction.FATAL


def is_output_truncated(finish_reason: str | None) -> bool:
    if not finish_reason:
        return False
    normalized = finish_reason.strip().lower()
    return normalized in ("length", "max_tokens")

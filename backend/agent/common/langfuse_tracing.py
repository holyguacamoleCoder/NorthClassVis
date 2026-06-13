"""
Optional Langfuse tracing for the agent loop.

Enable with LANGFUSE_PUBLIC_KEY + LANGFUSE_SECRET_KEY (and optionally LANGFUSE_ENABLED=1).
Supports LANGFUSE_HOST or LANGFUSE_BASE_URL (cloud default: https://cloud.langfuse.com).

When the SDK is missing or keys are unset, all context managers are no-ops.
"""

from __future__ import annotations

import os
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Iterator

_REDACT = os.environ.get("LANGFUSE_REDACT_CONTENT", "1").strip().lower() in (
    "1",
    "true",
    "yes",
    "on",
)

_trace_stats: ContextVar[dict[str, Any] | None] = ContextVar("lf_turn_stats", default=None)
_v2_trace: ContextVar[Any] = ContextVar("lf_v2_trace", default=None)
_client: Any = None
_client_checked = False
_use_modern_api: bool | None = None


def _env_flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


def _ensure_host_env() -> None:
    if os.environ.get("LANGFUSE_HOST", "").strip():
        return
    base = os.environ.get("LANGFUSE_BASE_URL", "").strip()
    if base:
        os.environ["LANGFUSE_HOST"] = base.rstrip("/")


def is_enabled() -> bool:
    if _env_flag("LANGFUSE_DISABLED") or os.environ.get(
        "LANGFUSE_TRACING_ENABLED", ""
    ).strip().lower() in ("0", "false", "no", "off"):
        return False
    if os.environ.get("LANGFUSE_ENABLED", "").strip().lower() in (
        "0",
        "false",
        "no",
        "off",
    ):
        return False
    pk = os.environ.get("LANGFUSE_PUBLIC_KEY", "").strip()
    sk = os.environ.get("LANGFUSE_SECRET_KEY", "").strip()
    if not pk or not sk:
        return False
    if _env_flag("LANGFUSE_ENABLED"):
        return True
    return True


def redact_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not _REDACT:
        return messages
    out: list[dict[str, Any]] = []
    for m in messages:
        if not isinstance(m, dict):
            out.append(m)
            continue
        row = dict(m)
        content = row.get("content")
        if isinstance(content, str):
            row["content"] = f"<redacted len={len(content)}>"
        elif content is not None:
            row["content"] = "<redacted>"
        out.append(row)
    return out


def redact_text(text: str, *, max_len: int = 4000) -> str:
    if not _REDACT:
        return text[:max_len] if text else ""
    if not text:
        return ""
    return f"<redacted len={len(text)}>"


def redact_params(params: dict[str, Any]) -> dict[str, Any]:
    safe = {k: v for k, v in params.items() if not str(k).startswith("_")}
    if not _REDACT:
        return safe
    out: dict[str, Any] = {}
    for k, v in safe.items():
        if isinstance(v, str) and len(v) > 200:
            out[k] = f"<redacted len={len(v)}>"
        else:
            out[k] = v
    return out


def _get_client() -> Any:
    global _client, _client_checked, _use_modern_api
    if not is_enabled():
        return None
    if _client_checked:
        return _client
    _client_checked = True
    _ensure_host_env()
    try:
        from langfuse import Langfuse, get_client  # type: ignore

        try:
            _client = get_client()
        except Exception:
            _client = Langfuse(
                public_key=os.environ.get("LANGFUSE_PUBLIC_KEY"),
                secret_key=os.environ.get("LANGFUSE_SECRET_KEY"),
                host=os.environ.get("LANGFUSE_HOST", "https://cloud.langfuse.com"),
            )
        _use_modern_api = hasattr(_client, "start_as_current_observation")
        return _client
    except ImportError:
        try:
            from langfuse import Langfuse  # type: ignore

            _client = Langfuse(
                public_key=os.environ.get("LANGFUSE_PUBLIC_KEY"),
                secret_key=os.environ.get("LANGFUSE_SECRET_KEY"),
                host=os.environ.get("LANGFUSE_HOST", "https://cloud.langfuse.com"),
            )
            _use_modern_api = hasattr(_client, "start_as_current_observation")
            return _client
        except ImportError:
            _client = None
            _use_modern_api = False
            return None
    except Exception:
        _client = None
        return None


def flush() -> None:
    client = _get_client()
    if client is None:
        return
    try:
        client.flush()
    except Exception:
        pass


def _new_trace_context() -> dict[str, str]:
    """Force a fresh Langfuse/OTel trace (one per user message / HTTP job)."""
    try:
        from langfuse import create_trace_id  # type: ignore

        trace_id = create_trace_id()
    except Exception:
        trace_id = uuid.uuid4().hex
    parent_span_id = uuid.uuid4().hex[:16]
    return {"trace_id": trace_id, "parent_span_id": parent_span_id}


def _apply_root_trace_labels(
    client: Any,
    root: Any,
    *,
    name: str,
    session_id: str | None,
    metadata: dict[str, Any],
    input_value: str,
) -> None:
    """Set trace-level name/session so the Langfuse UI lists one trace per job."""
    for caller in (
        lambda: client.update_current_trace(
            name=name,
            session_id=session_id,
            metadata=metadata,
            input=input_value,
        ),
        lambda: root.update_trace(
            name=name,
            session_id=session_id,
            metadata=metadata,
            input=input_value,
        ),
        lambda: root.update(
            metadata={**metadata, "trace_name": name, "session_id": session_id},
        ),
    ):
        try:
            caller()
            return
        except Exception:
            continue


def _usage_details(resp: Any) -> dict[str, int] | None:
    usage = getattr(resp, "usage", None)
    if usage is None:
        return None
    prompt = getattr(usage, "prompt_tokens", None) or getattr(usage, "input_tokens", None)
    completion = getattr(usage, "completion_tokens", None) or getattr(
        usage, "output_tokens", None
    )
    details: dict[str, int] = {}
    if prompt is not None:
        details["input"] = int(prompt)
    if completion is not None:
        details["output"] = int(completion)
    return details or None


def summarize_llm_output(resp: Any) -> Any:
    if not resp or not getattr(resp, "choices", None):
        return ""
    msg = resp.choices[0].message
    content = getattr(msg, "content", None) or ""
    tool_calls = getattr(msg, "tool_calls", None) or []
    if tool_calls:
        names = []
        for t in tool_calls:
            fn = getattr(t, "function", None)
            names.append(getattr(fn, "name", None) or getattr(t, "name", ""))
        return {"content": redact_text(str(content), max_len=500), "tool_calls": names}
    return redact_text(str(content))


@contextmanager
def user_turn_trace(
    *,
    session_id: str | None,
    job_id: str | None,
    user_message: str,
    permission_mode: str | None = None,
    extra_metadata: dict[str, Any] | None = None,
) -> Iterator[None]:
    """One user message / HTTP job = one Langfuse trace."""
    client = _get_client()
    stats: dict[str, Any] = {"turns": 0}
    token_stats = _trace_stats.set(stats)
    if client is None:
        try:
            yield
        finally:
            _trace_stats.reset(token_stats)
        return

    name = (user_message or "").strip()[:80] or "agent_turn"
    meta = {
        "job_id": job_id,
        "permission_mode": permission_mode,
        "app": "northclass.agent",
    }
    if extra_metadata:
        meta.update(extra_metadata)
    inp = (
        redact_text(user_message, max_len=500)
        if _REDACT
        else (user_message or "")[:2000]
    )

    if _use_modern_api:
        trace_context = _new_trace_context()
        trace_label = f"job-{job_id}" if job_id else name
        try:
            from langfuse import propagate_attributes  # type: ignore

            with propagate_attributes(
                session_id=session_id,
                metadata=meta,
                trace_name=trace_label,
            ):
                with client.start_as_current_observation(
                    as_type="span",
                    name=name,
                    input=inp,
                    metadata=meta,
                    trace_context=trace_context,
                ) as root:
                    _apply_root_trace_labels(
                        client,
                        root,
                        name=trace_label,
                        session_id=session_id,
                        metadata=meta,
                        input_value=inp,
                    )
                    try:
                        yield
                    finally:
                        root.update(
                            output={
                                "continue_reason": stats.get("continue_reason"),
                                "turns": stats.get("turns"),
                            }
                        )
                        _apply_root_trace_labels(
                            client,
                            root,
                            name=trace_label,
                            session_id=session_id,
                            metadata={
                                **meta,
                                "continue_reason": stats.get("continue_reason"),
                                "turns": stats.get("turns"),
                            },
                            input_value=inp,
                        )
        finally:
            _trace_stats.reset(token_stats)
            flush()
        return

    # Langfuse SDK v2
    trace = client.trace(name=name, session_id=session_id, metadata=meta, input=inp)
    token_trace = _v2_trace.set(trace)
    try:
        yield
    finally:
        try:
            trace.update(
                output={
                    "continue_reason": stats.get("continue_reason"),
                    "turns": stats.get("turns"),
                }
            )
        except Exception:
            pass
        _v2_trace.reset(token_trace)
        _trace_stats.reset(token_stats)
        flush()


def record_loop_end(*, continue_reason: str | None, turn_count: int) -> None:
    stats = _trace_stats.get()
    if stats is not None:
        stats["continue_reason"] = continue_reason
        stats["turns"] = turn_count


@contextmanager
def agent_turn_span(*, turn: int) -> Iterator[None]:
    client = _get_client()
    if client is None:
        yield
        return
    stats = _trace_stats.get()
    if stats is not None:
        stats["turns"] = max(int(stats.get("turns") or 0), turn + 1)

    span_name = f"agent_turn_{turn}"
    if _use_modern_api:
        with client.start_as_current_observation(
            as_type="span",
            name=span_name,
            metadata={"turn": turn},
        ):
            yield
        return

    trace = _v2_trace.get()
    if trace is None:
        yield
        return
    span = trace.span(name=span_name, metadata={"turn": turn})
    try:
        yield
    finally:
        span.end()


@contextmanager
def llm_generation(
    *,
    name: str,
    model: str,
    messages: list[dict[str, Any]],
    tools_count: int = 0,
    metadata: dict[str, Any] | None = None,
) -> Iterator[Any]:
    client = _get_client()
    if client is None:
        yield None
        return

    meta = {**(metadata or {}), "tools_count": tools_count}
    inp = redact_messages(messages)

    if _use_modern_api:
        with client.start_as_current_observation(
            as_type="generation",
            name=name,
            model=model,
            input=inp,
            metadata=meta,
        ) as gen:
            try:
                yield gen
            except Exception as exc:
                gen.update(level="ERROR", status_message=str(exc))
                raise
        return

    trace = _v2_trace.get()
    if trace is None:
        yield None
        return
    gen = trace.generation(name=name, model=model, input=inp, metadata=meta)
    try:
        yield gen
    except Exception as exc:
        gen.end(level="ERROR", status_message=str(exc))
        raise


def end_llm_generation(
    gen: Any,
    *,
    resp: Any = None,
    output_text: str = "",
    error: str | None = None,
) -> None:
    if gen is None:
        return
    if error:
        try:
            gen.update(level="ERROR", status_message=error)
        except Exception:
            try:
                gen.end(level="ERROR", status_message=error)
            except Exception:
                pass
        return

    output: Any = summarize_llm_output(resp) if resp is not None else redact_text(output_text)
    usage = _usage_details(resp) if resp is not None else None
    try:
        if usage:
            gen.update(output=output, usage_details=usage)
        else:
            gen.update(output=output)
    except Exception:
        try:
            gen.end(output=output, usage=usage)
        except Exception:
            pass


@contextmanager
def tool_span(*, tool: str, params: dict[str, Any]) -> Iterator[Any]:
    client = _get_client()
    if client is None:
        yield None
        return

    safe = redact_params(params)
    if _use_modern_api:
        with client.start_as_current_observation(
            as_type="tool",
            name=tool or "unknown",
            input=safe,
        ) as span:
            try:
                yield span
            except Exception as exc:
                span.update(level="ERROR", status_message=str(exc))
                raise
        return

    trace = _v2_trace.get()
    if trace is None:
        yield None
        return
    span = trace.span(name=tool or "unknown", input=safe)
    try:
        yield span
    except Exception as exc:
        span.end(level="ERROR", status_message=str(exc))
        raise


def end_tool_span(
    span: Any,
    *,
    output: str,
    is_error: bool = False,
) -> None:
    if span is None:
        return
    preview = redact_text(output or "", max_len=8000)
    level = "ERROR" if is_error else "DEFAULT"
    try:
        span.update(output=preview, level=level)
    except Exception:
        try:
            span.end(output=preview, level=level)
        except Exception:
            pass


def is_tool_result_error(content: str) -> bool:
    text = (content or "").strip()
    return text.startswith(("Error:", "Permission denied", "Tool blocked"))

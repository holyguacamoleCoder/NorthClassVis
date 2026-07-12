"""Detect LLM provider quirks from env (DeepSeek thinking mode, etc.)."""

from __future__ import annotations

import os


def _base_url() -> str:
    return (os.environ.get("OPENAI_BASE_URL") or "https://api.openai.com/v1").strip().lower()


def is_deepseek_provider(base_url: str | None = None) -> bool:
    url = (base_url or _base_url()).lower()
    return "deepseek" in url


def deepseek_thinking_enabled(base_url: str | None = None) -> bool:
    """
    Whether to enable DeepSeek thinking mode on chat.completions requests.

    Set DEEPSEEK_THINKING_ENABLED=0|false to disable (avoids reasoning_content protocol).
    Ignored for non-DeepSeek base URLs.
    """
    if not is_deepseek_provider(base_url):
        return False
    raw = (os.environ.get("DEEPSEEK_THINKING_ENABLED") or "true").strip().lower()
    return raw not in ("0", "false", "no", "off")


def should_include_reasoning_content_in_api(base_url: str | None = None) -> bool:
    """Pass stored assistant reasoning_content back to the API (required for DeepSeek tool loops)."""
    return is_deepseek_provider(base_url) and deepseek_thinking_enabled(base_url)

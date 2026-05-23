"""Backward-compatible exports; prefer tools.runtime."""

import runtime_bootstrap  # noqa: F401

from context import maybe_persist_output
from context.config import DEFAULT_CONFIG

from .definitions.registry import TOOL_DISPATCHER
from .runtime.pipeline.preprocess import dedupe_tool_calls, parse_args
from .runtime.executor import execute_tool_calls

__all__ = [
    "DEFAULT_CONFIG",
    "TOOL_DISPATCHER",
    "dedupe_tool_calls",
    "execute_tool_calls",
    "maybe_persist_output",
    "parse_args",
]

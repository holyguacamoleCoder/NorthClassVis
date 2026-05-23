"""Tool dispatcher — generated from definitions.manifest."""

from .manifest import (
    CONCURRENCY_LIMIT,
    CONCURRENCY_SAFE_TOOL,
    CONCURRENCY_UNSAFE_TOOL,
    MANIFEST,
    MANIFEST_BY_NAME,
    ToolDefinition,
    build_dispatcher,
)

TOOL_DISPATCHER = build_dispatcher()

__all__ = [
    "CONCURRENCY_LIMIT",
    "CONCURRENCY_SAFE_TOOL",
    "CONCURRENCY_UNSAFE_TOOL",
    "MANIFEST",
    "MANIFEST_BY_NAME",
    "TOOL_DISPATCHER",
    "ToolDefinition",
    "build_dispatcher",
]

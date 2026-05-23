"""Tool execution runtime (import submodules directly to avoid heavy deps)."""

from .pipeline.preprocess import dedupe_tool_calls, parse_args

__all__ = [
    "dedupe_tool_calls",
    "execute_tool_calls",
    "parse_args",
]


def __getattr__(name: str):
    if name == "execute_tool_calls":
        from .executor import execute_tool_calls

        return execute_tool_calls
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

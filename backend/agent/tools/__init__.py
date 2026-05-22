from .schemas import TOOLS

__all__ = [
    "TOOLS",
    "execute_tool_calls",
]


def __getattr__(name: str):
    if name == "execute_tool_calls":
        from .executor import execute_tool_calls

        return execute_tool_calls
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

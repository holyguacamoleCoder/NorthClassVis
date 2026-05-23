"""OpenAI tool schemas — generated from definitions.manifest."""

from .manifest import MANIFEST, ToolDefinition, build_openai_tools

TOOLS: list[dict] = build_openai_tools()

__all__ = ["MANIFEST", "ToolDefinition", "TOOLS", "build_openai_tools"]

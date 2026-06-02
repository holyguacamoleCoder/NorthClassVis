"""memory_delivery parsing."""

import sys
from pathlib import Path

AGENT_ROOT = Path(__file__).resolve().parents[1]
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))

from memory_delivery import memory_event_from_tool, parse_memory_tool_result  # noqa: E402


def test_parse_memory_updated():
    text = "[Memory updated: target=user, type=user, path=backend/.agent/memory/user_profile.md, action=add]"
    parsed = parse_memory_tool_result(text)
    assert parsed is not None
    assert parsed["target"] == "user"
    assert parsed["action"] == "add"


def test_memory_event_skips_errors():
    assert memory_event_from_tool("memory", "Error: old_text not found", {}) is None

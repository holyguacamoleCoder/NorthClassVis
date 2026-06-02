"""memory / save_memory tools and MemoryManager."""

import sys
import tempfile
from pathlib import Path

import pytest

AGENT_ROOT = Path(__file__).resolve().parents[1]
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))

import runtime_bootstrap  # noqa: F401, E402

from common.memory import MemoryManager, get_memory_manager  # noqa: E402
from memory_delivery import memory_event_from_tool, parse_memory_tool_result  # noqa: E402
from permission import CapabilityMode, filter_tools  # noqa: E402
from permission.modes import MODE_TOOL_ALLOWLIST  # noqa: E402
from tools.definitions.schemas import TOOLS  # noqa: E402
from tools.handlers.memory import run_memory  # noqa: E402
from tools.handlers.save_memory import run_save_memory  # noqa: E402


@pytest.fixture
def mem_dir(monkeypatch):
    base = Path(tempfile.mkdtemp())
    monkeypatch.setattr(
        "common.memory._default_memory",
        None,
    )
    mgr = MemoryManager(memory_dir=base / "memory")
    monkeypatch.setattr("common.memory._default_memory", mgr)
    monkeypatch.setattr(
        "tools.handlers.memory.get_memory_manager",
        lambda: mgr,
    )
    monkeypatch.setattr(
        "tools.handlers.save_memory.get_memory_manager",
        lambda: mgr,
    )
    return mgr


def test_memory_tool_in_analyze_mode():
    names = {t["function"]["name"] for t in TOOLS}
    assert "memory" in names
    assert "save_memory" in names
    visible = {t["function"]["name"] for t in filter_tools(TOOLS, CapabilityMode.ANALYZE)}
    assert "memory" in visible
    assert "memory" in MODE_TOOL_ALLOWLIST[CapabilityMode.ANALYZE]


def test_run_memory_add_user(mem_dir):
    out = run_memory("add", "user", content="Class1 报告偏好表格呈现")
    assert out.startswith("[Memory updated:")
    assert "target=user" in out
    mem_dir.load_all()
    entry = mem_dir.get_entry("user_profile")
    assert entry is not None
    assert "Class1" in entry["content"]


def test_run_memory_replace_and_remove(mem_dir):
    run_memory("add", "memory", content="Use query_data before aggregate")
    out = run_memory(
        "replace",
        "memory",
        content="Always query_data then aggregate_data",
        old_text="query_data before aggregate",
    )
    assert "action=replace" in out
    mem_dir.load_all()
    assert "aggregate_data" in mem_dir.get_entry("agent_notes")["content"]
    out = run_memory(
        "remove",
        "memory",
        old_text="Always query_data then aggregate_data",
    )
    assert "action=remove" in out
    mem_dir.load_all()
    assert "aggregate_data" not in (mem_dir.get_entry("agent_notes") or {}).get("content", "")


def test_run_save_memory_named_file(mem_dir):
    out = run_save_memory(
        "report_style",
        "Class1 report layout",
        "user",
        "Prefer tables over long prose.",
    )
    assert "[Memory saved:" in out
    mem_dir.load_all()
    assert "report_style" in mem_dir.memories
    section = mem_dir.load_memory_prompt()
    assert "Prefer tables" in section


def test_save_memory_rejects_secrets(mem_dir):
    out = run_save_memory("leak", "bad", "user", "api_key=sk-secret123")
    assert out.startswith("Error:")


def test_update_entry_via_manager(mem_dir):
    run_save_memory("style", "Report style", "user", "Use tables.")
    out = mem_dir.update_entry("style", content="Use bullet lists.")
    assert "saved" in out.lower() or "overwritten" in out.lower()
    mem_dir.load_all()
    assert "bullet" in mem_dir.get_entry("style")["content"]


def test_update_enabled_only_skips_content_validation(mem_dir):
    """侧栏仅切换 enabled 时不应因正文校验失败而无法停用。"""
    mem_dir.memory_dir.mkdir(parents=True, exist_ok=True)
    body = "SELECT column layout from schema " + ("x" * 420)
    (mem_dir.memory_dir / "legacy_dump.md").write_text(
        f"---\nname: legacy_dump\ndescription: old\ntype: user\nenabled: true\n---\n{body}\n",
        encoding="utf-8",
    )
    mem_dir.load_all()
    assert mem_dir.validate_content(body) is not None
    assert mem_dir.get_entry("legacy_dump")["enabled"] is True
    out = mem_dir.update_entry("legacy_dump", enabled=False)
    assert not out.startswith("Error:")
    mem_dir.load_all()
    assert mem_dir.get_entry("legacy_dump")["enabled"] is False
    assert mem_dir._enabled_memories().get("legacy_dump") is None


def test_create_memory_via_save(mem_dir):
    out = mem_dir.save_memory("manual_note", "Teacher added", "user", "Prefer bullet lists in reports.")
    assert "[Memory saved:" in out
    mem_dir.load_all()
    entry = mem_dir.get_entry("manual_note")
    assert entry is not None
    assert "bullet" in entry["content"]


def test_delete_entry(mem_dir):
    run_save_memory("tmp_mem", "temp", "feedback", "fix chart labels")
    out = mem_dir.delete_entry("tmp_mem")
    assert "removed" in out.lower()
    mem_dir.load_all()
    assert "tmp_mem" not in mem_dir.memories


def test_memory_event_from_tool():
    text = "[Memory saved: name=foo, type=user, path=backend/.agent/memory/foo.md, action=created]"
    event = memory_event_from_tool("save_memory", text, {"name": "foo"})
    assert event is not None
    assert event.get("name") == "foo"
    assert parse_memory_tool_result(text) is not None

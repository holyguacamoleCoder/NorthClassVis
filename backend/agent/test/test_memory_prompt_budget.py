"""Memory prompt index mode and update_entry."""

import sys
import tempfile
from pathlib import Path

import pytest

AGENT_ROOT = Path(__file__).resolve().parents[1]
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))

import runtime_bootstrap  # noqa: F401, E402

from common.memory import (  # noqa: E402
    MAX_PROMPT_MEMORY_CHARS,
    MemoryManager,
)


@pytest.fixture
def mem_dir():
    return Path(tempfile.mkdtemp()) / "memory"


def test_index_mode_uses_preview_not_full_body(mem_dir):
    mgr = MemoryManager(memory_dir=mem_dir)
    long_body = "X" * 500
    mgr.save_memory("big_fact", "Long note", "user", long_body)
    index = mgr.load_memory_prompt(mode="index")
    full = mgr.load_memory_prompt(mode="full")
    assert long_body not in index
    assert "X" * 50 in index or "…" in index
    assert long_body in full


def test_index_mode_respects_char_budget(mem_dir):
    mgr = MemoryManager(memory_dir=mem_dir)
    for i in range(30):
        mgr.save_memory(f"fact_{i}", f"Desc {i}", "project", f"Content block number {i} " * 8)
    index = mgr.load_memory_prompt(mode="index")
    assert len(index) <= MAX_PROMPT_MEMORY_CHARS + 120
    assert "摘要模式" in index


def test_update_entry(mem_dir):
    mgr = MemoryManager(memory_dir=mem_dir)
    mgr.save_memory("style", "Report style", "user", "Use tables.")
    out = mgr.update_entry("style", content="Use bullet lists.")
    assert "saved" in out.lower() or "overwritten" in out.lower()
    mgr.load_all()
    assert "bullet" in mgr.get_entry("style")["content"]

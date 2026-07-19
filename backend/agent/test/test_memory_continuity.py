"""Session schema cache and dream consolidator."""

from __future__ import annotations

import json
import sys
from pathlib import Path

AGENT_ROOT = Path(__file__).resolve().parents[1]
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))

import runtime_bootstrap  # noqa: F401, E402

from common.dream import DreamConsolidator  # noqa: E402
from common.memory import MemoryManager  # noqa: E402
from common.prompts import COMPACT_SUMMARY_USER_TEMPLATE  # noqa: E402
from data.schema_cache import get_cached_schema, put_cached_schema  # noqa: E402
from session.models import ChatSession  # noqa: E402
from session.store import FileSessionStore  # noqa: E402


def test_compact_prompt_requires_dataset_handles():
    assert "dataset_id" in COMPACT_SUMMARY_USER_TEMPLATE
    assert "result_ref" in COMPACT_SUMMARY_USER_TEMPLATE


def test_schema_cache_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr("data.schema_cache.AGENT_STATE_DIR", tmp_path, raising=False)
    payload = {
        "resource": "student_info",
        "columns": [{"name": "student_ID", "type": "string"}],
        "sample_rows": [["a"], ["b"], ["c"], ["d"], ["e"], ["f"]],
        "row_count_estimate": 10,
    }
    put_cached_schema("s1", "student_info", payload, {"class": "Class1"})
    hit = get_cached_schema("s1", "student_info", {"class": "Class1"})
    assert hit is not None
    assert hit["resource"] == "student_info"
    assert len(hit["sample_rows"]) == 5
    miss = get_cached_schema("s1", "student_info", {"class": "Class2"})
    assert miss is None


def test_dream_removes_empty_and_duplicate(tmp_path):
    mem_dir = tmp_path / "memory"
    mgr = MemoryManager(memory_dir=mem_dir)
    mgr.save_memory("style_a", "tabs", "user", "Always use tabs.")
    mgr.save_memory("style_b", "tabs again", "user", "Always use tabs.")
    empty = mem_dir / "empty_note.md"
    empty.write_text(
        "---\nname: empty_note\ndescription: x\ntype: project\nenabled: true\n---\n\n",
        encoding="utf-8",
    )
    dream = DreamConsolidator(memory_dir=mem_dir)
    dream.session_count = 10
    dream.last_consolidation_time = 0
    dream.last_scan_time = 0
    phases = dream.consolidate(force=True)
    assert len(phases) == 4
    mgr2 = MemoryManager(memory_dir=mem_dir)
    mgr2.load_all()
    assert "empty_note" not in mgr2.memories
    # One of the duplicate style_* should remain
    style_keys = [k for k in mgr2.memories if k.startswith("style_")]
    assert len(style_keys) == 1


def test_visual_links_persist_in_session_store(tmp_path):
    store = FileSessionStore(root=tmp_path / "sessions")
    session = ChatSession(
        id="abc123",
        title="t",
        permission_mode="analyze",
        created_at=1.0,
        updated_at=1.0,
        visual_links=[{"view": "WeekView", "params": {"week": 1}, "label": "w1"}],
    )
    store.save(session)
    loaded = store.load("abc123")
    assert loaded is not None
    assert loaded.visual_links[0]["view"] == "WeekView"
    assert (tmp_path / "sessions" / "abc123" / "visual_links.json").is_file()

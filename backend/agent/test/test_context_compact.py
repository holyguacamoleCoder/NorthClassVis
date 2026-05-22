import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

AGENT_DIR = Path(__file__).resolve().parents[1]
if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))

from context.config import ContextCompactConfig
from context.macro_compact import build_compacted_messages, compact_history, extract_tail_messages
from context.micro_compact import compact_tool_content, micro_compact_messages
from context.persist import COMPACTED_TOOL_PLACEHOLDER
from context.persist import maybe_persist_output
from context.state import CompactState, track_recent_file
from tools.runtime.dedupe import dedupe_tool_calls
from tools.runtime.executor import execute_tool_calls


@pytest.fixture
def compact_config(tmp_path):
    return ContextCompactConfig(
        context_limit=1000,
        persist_threshold=100,
        preview_chars=20,
        keep_recent_tool_results=2,
        transcript_dir=tmp_path / "transcripts",
        tool_results_dir=tmp_path / "tool-results",
        enabled=True,
    )


def test_maybe_persist_writes_file_and_preview(compact_config, tmp_path):
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(
        "context.persist.DATA_DIR",
        tmp_path,
        raising=False,
    )
    compact_config = ContextCompactConfig(
        persist_threshold=50,
        preview_chars=10,
        tool_results_dir=tmp_path / "tool-results",
    )
    big = "x" * 200
    out = maybe_persist_output("call-1", big, config=compact_config)
    assert "<persisted-output>" in out
    stored = compact_config.tool_results_dir / "call-1.txt"
    assert stored.exists()
    assert stored.read_text(encoding="utf-8") == big
    monkeypatch.undo()


def test_micro_compact_keeps_recent_tool_messages(compact_config):
    messages = [
        {"role": "tool", "tool_call_id": f"id-{i}", "content": "o" * 200}
        for i in range(5)
    ]
    compacted_count = micro_compact_messages(messages, config=compact_config)
    assert compacted_count == 3
    assert messages[-1]["content"] == "o" * 200
    assert messages[-2]["content"] == "o" * 200
    assert "Earlier tool result compacted" in messages[0]["content"]


def test_track_recent_file_max_five():
    state = CompactState()
    for i in range(7):
        track_recent_file(state, f"f{i}.txt", max_files=5)
    assert state.recent_files == [f"f{i}.txt" for i in range(2, 7)]


def test_extract_tail_keeps_assistant_and_tools(compact_config):
    messages = [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "", "tool_calls": [{"id": "1"}]},
        {"role": "tool", "tool_call_id": "1", "content": "result"},
    ]
    tail = extract_tail_messages(messages, config=compact_config)
    assert len(tail) == 2
    assert tail[0]["role"] == "assistant"
    assert tail[1]["role"] == "tool"


def test_compact_history_uses_llm_and_writes_transcript(compact_config, tmp_path):
    llm = MagicMock()
    llm.chat_text.return_value = "summary text"
    state = CompactState()
    messages = [{"role": "user", "content": "goal"}]
    new_messages = compact_history(
        messages,
        llm,
        state,
        config=compact_config,
        reason="auto",
    )
    assert state.has_compacted
    assert state.last_summary == "summary text"
    assert "compacted" in new_messages[0]["content"].lower()
    assert list(compact_config.transcript_dir.glob("transcript_*.jsonl"))
    llm.chat_text.assert_called_once()


def test_build_compacted_messages_includes_focus_and_recent_files():
    state = CompactState(recent_files=["a.py", "b.py"])
    msgs = build_compacted_messages("sum", focus="finish tests", compact_state=state)
    text = msgs[0]["content"]
    assert "sum" in text
    assert "finish tests" in text
    assert "a.py" in text


def test_execute_tool_calls_persists_large_output(compact_config, monkeypatch):
    monkeypatch.setattr(
        "tools.runtime.postprocess.maybe_persist_output",
        lambda call_id, content: maybe_persist_output(call_id, content, config=compact_config),
    )
    monkeypatch.setattr(
        "tools.runtime.postprocess.DEFAULT_CONFIG",
        compact_config,
    )
    monkeypatch.setattr(
        "tools.runtime.executor.TOOL_DISPATCHER",
        {"read_file": lambda **kwargs: "z" * 500},
    )
    results = execute_tool_calls(
        [{"id": "tc-1", "name": "read_file", "arguments": {"path": "x.txt"}}],
        compact_state=CompactState(),
    )
    assert "<persisted-output>" in results[0]["content"]


def test_micro_compact_preserves_tabular_summary(compact_config):
    payload = json.dumps(
        {
            "resource": "submit_record_joined",
            "rows": [],
            "meta": {
                "result_ref": "query-results/abc.json",
                "rows_scanned": 100,
                "truncated": True,
            },
        },
        ensure_ascii=False,
    )
    compacted = compact_tool_content(payload)
    assert COMPACTED_TOOL_PLACEHOLDER in compacted
    assert "result_ref=query-results/abc.json" in compacted
    assert "rows_scanned=100" in compacted


def test_dedupe_tool_calls_drops_identical():
    calls = [
        {"id": "a", "name": "query_data", "arguments": {"resource": "x", "class": "Class1"}},
        {"id": "b", "name": "query_data", "arguments": {"resource": "x", "class": "Class1"}},
    ]
    out = dedupe_tool_calls(calls)
    assert len(out) == 1
    assert out[0]["id"] == "a"

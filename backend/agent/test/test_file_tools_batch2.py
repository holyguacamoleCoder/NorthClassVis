"""Batch-2 file tool manifest and consult list_files loop guard."""

import json
import sys
from pathlib import Path

import pytest

AGENT_ROOT = Path(__file__).resolve().parents[1]
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))

import runtime_bootstrap  # noqa: F401, E402

from loop import AgentLoop  # noqa: E402
from loop_state import LoopState  # noqa: E402
from permission import CapabilityMode, PermissionManager  # noqa: E402
from tools.definitions.manifest import MANIFEST  # noqa: E402
from tools.handlers.base_tool import run_list_files, run_read_file  # noqa: E402


def _tool(name: str):
    return next(d for d in MANIFEST if d.name == name)


def test_manifest_read_file_batch2_schema():
    read = _tool("read_file")
    limit = read.parameters["properties"]["limit"]
    assert limit["minimum"] == 1
    assert limit["maximum"] == 5000
    assert "50000" in limit["description"] or "50000" in read.description
    assert "consult" in read.description.lower()
    assert "inspect_schema" in read.description


def test_manifest_list_files_batch2_schema():
    lst = _tool("list_files")
    assert lst.defaults == {"path": ".", "recursive": False, "limit": 200}
    limit = lst.parameters["properties"]["limit"]
    assert limit["maximum"] == 500
    assert "recursive" in lst.parameters["properties"]
    assert "inspect_schema" in lst.description
    assert "query_data" in lst.description


def test_manifest_write_edit_batch2():
    write = _tool("write_file")
    edit = _tool("edit_file")
    for defn in (write, edit):
        assert "produce" in defn.description
        assert "reports" in defn.description
        path_desc = defn.parameters["properties"]["path"]["description"]
        assert "reports" in path_desc and "exports" in path_desc


def test_read_file_status_header(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    data = tmp_path / "data" / "reports"
    data.mkdir(parents=True)
    sample = data / "note.md"
    sample.write_text("line1\nline2\nline3\n", encoding="utf-8")
    monkeypatch.setattr(
        "tools.handlers.base_tool.DATA_DIR",
        tmp_path / "data",
    )
    out = run_read_file("reports/note.md", limit=2)
    assert out.startswith("[Read OK:")
    assert "truncated=True" in out.split("\n", 1)[0]


def test_consult_list_files_loop_guard():
    perm = PermissionManager(mode=CapabilityMode.CONSULT)
    loop = AgentLoop(LoopState(messages=[]), permission=perm)
    calls = [
        {
            "id": "1",
            "name": "list_files",
            "arguments": json.dumps({"path": "Data_SubmitRecord"}),
        }
    ]
    assert loop._should_break_consult_list_loop(calls) is False
    for _ in range(3):
        loop._should_break_consult_list_loop(calls)
    assert loop._should_break_consult_list_loop(calls) is True

    analyze_perm = PermissionManager(mode=CapabilityMode.ANALYZE)
    loop2 = AgentLoop(LoopState(messages=[]), permission=analyze_perm)
    for _ in range(5):
        assert loop2._should_break_consult_list_loop(calls) is False

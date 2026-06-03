"""Session deliverables registry."""

import sys
from pathlib import Path

AGENT_ROOT = Path(__file__).resolve().parents[1]
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))

import runtime_bootstrap  # noqa: F401, E402

from session.deliverables_registry import (  # noqa: E402
    format_deliverables_prompt,
    list_deliverables,
    record_deliverable_from_tool,
)


def test_record_and_prompt(monkeypatch, tmp_path):
    monkeypatch.setattr("session.deliverables_registry.AGENT_STATE_DIR", tmp_path)
    sid = "sess_test01"
    record_deliverable_from_tool(
        sid,
        rel_path="reports/student/x/diagnosis.md",
        label="diagnosis",
        user_turn=2,
    )
    rows = list_deliverables(sid)
    assert len(rows) == 1
    assert rows[0].path == "reports/student/x/diagnosis.md"
    block = format_deliverables_prompt(sid)
    assert "reports/student/x/diagnosis.md" in block
    assert "本会话" in block

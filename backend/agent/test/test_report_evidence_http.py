"""Tests for load_reference _shared prepend and report_evidence HTTP field."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

_BACKEND_ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

from agent.http.adapter import adapt_legacy_query_response  # noqa: E402
from agent.skills.references import read_reference_text  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_load_reference_prepends_shared():
    if not (REPO_ROOT / "skills" / "report-writing" / "references" / "_shared.md").is_file():
        pytest.skip("skills not in repo layout")
    found = read_reference_text("student")
    assert found is not None
    _rel, text = found
    assert "report-chart" in text
    assert "Student Report Reference" in text
    assert text.index("report-chart") < text.index("Student Report Reference")


def test_adapt_legacy_report_evidence_from_deliverable(tmp_path, monkeypatch):
    from common.paths import DATA_DIR

    rel = "reports/student/J9/diagnosis.md"
    dest = DATA_DIR / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    body = """# R

## evidence

- 周趋势 [@ref:query-results/fake.json]
- 统计 [@ds:ds_abc123def01]
"""
    dest.write_text(body, encoding="utf-8")

    messages = [
        {"role": "user", "content": "写报告"},
        {
            "role": "assistant",
            "tool_calls": [
                {
                    "id": "w1",
                    "type": "function",
                    "function": {
                        "name": "write_file",
                        "arguments": json.dumps({"path": rel}),
                    },
                }
            ],
        },
        {"role": "tool", "tool_call_id": "w1", "content": f"[Write OK: path={rel}, bytes=10]"},
        {"role": "assistant", "content": "报告已写入。"},
    ]
    out = adapt_legacy_query_response(messages)
    assert "report_evidence" in out
    assert len(out["report_evidence"]) == 2
    assert out["process_evidence"] == out["evidence"]

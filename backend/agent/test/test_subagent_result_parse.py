"""Tests for subagent result parsing."""

from __future__ import annotations

import runtime_bootstrap  # noqa: F401, E402

from subagent.result_parse import parse_subagent_tool_result


def test_parse_subagent_tool_result_ok():
    text = """[SubAgent data_analyst OK]
turns: 3
refs:
  - query-results/abc.json
summary:
班级均分 1.46，周 peak 下降。
"""
    parsed = parse_subagent_tool_result(text)
    assert parsed["ok"] is True
    assert parsed["kind"] == "data_analyst"
    assert parsed["turns"] == 3
    assert parsed["refs"] == ["query-results/abc.json"]
    assert "1.46" in parsed["summary"]


def test_parse_subagent_tool_result_fail():
    text = """[SubAgent report_writer FAIL]
turns: 16
error: max_turns exceeded
summary:
(empty)
"""
    parsed = parse_subagent_tool_result(text)
    assert parsed["ok"] is False
    assert parsed["kind"] == "report_writer"
    assert parsed["error"] == "max_turns exceeded"

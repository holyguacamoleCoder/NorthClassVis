"""Tests for sub-agent delegation."""

from __future__ import annotations

import runtime_bootstrap  # noqa: F401, E402

from subagent.kinds import (
    SubAgentKind,
    filter_subagent_tools,
    list_subagent_kinds,
    resolve_kind,
)
from subagent.prompts import build_subagent_system_prompt
from subagent.runner import SubAgentResult
from tools.definitions.manifest import MANIFEST
from tools.definitions.schemas import TOOLS


def test_resolve_kind_aliases():
    assert resolve_kind("data_analyst") == SubAgentKind.DATA_ANALYST
    assert resolve_kind("analyst") == SubAgentKind.DATA_ANALYST
    assert resolve_kind("report_writer") == SubAgentKind.REPORT_WRITER
    assert resolve_kind("review") == SubAgentKind.REPORT_REVIEWER
    assert resolve_kind("unknown") is None


def test_filter_subagent_tools_excludes_run_subagent():
    schemas = [t.openai_tool() for t in MANIFEST]
    analyst_tools = filter_subagent_tools(schemas, SubAgentKind.DATA_ANALYST)
    names = {s["function"]["name"] for s in analyst_tools}
    assert "query_data" in names
    assert "run_subagent" not in names


def test_report_writer_has_write_tools():
    schemas = [t.openai_tool() for t in MANIFEST]
    names = {
        s["function"]["name"]
        for s in filter_subagent_tools(schemas, SubAgentKind.REPORT_WRITER)
    }
    assert "write_file" in names
    assert "edit_file" in names
    assert "query_data" not in names


def test_subagent_result_format():
    text = SubAgentResult(
        ok=True,
        kind="data_analyst",
        summary="班级均分 1.46",
        turns=3,
        refs=["query-results/abc.json"],
    ).format_tool_result()
    assert "[SubAgent data_analyst OK]" in text
    assert "query-results/abc.json" in text
    assert "班级均分" in text


def test_list_subagent_kinds():
    rows = list_subagent_kinds()
    assert len(rows) == 3
    assert {r["id"] for r in rows} == {
        "data_analyst",
        "report_writer",
        "report_reviewer",
    }


def test_prompts_per_kind():
    assert "analysis brief" in build_subagent_system_prompt(SubAgentKind.DATA_ANALYST)
    assert "分章写入" in build_subagent_system_prompt(SubAgentKind.REPORT_WRITER)
    assert "review_report" in build_subagent_system_prompt(SubAgentKind.REPORT_REVIEWER)


def test_manifest_includes_run_subagent():
    names = {t.name for t in MANIFEST}
    assert "run_subagent" in names
    openai_names = {t["function"]["name"] for t in TOOLS}
    assert "run_subagent" in openai_names

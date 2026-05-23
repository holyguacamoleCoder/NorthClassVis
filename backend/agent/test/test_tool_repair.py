import sys
from pathlib import Path

import pytest

import runtime_bootstrap  # noqa: F401, E402 — agent before backend/tools on sys.path

from permission.modes import MODE_TOOL_ALLOWLIST, CapabilityMode
from tools.runtime.pipeline.repair import (
    apply_arg_repairs,
    normalize_tool_name,
    repair_tool_call,
    resolve_tool_name,
)
from tools.runtime.pipeline.specs import TOOL_SPECS, build_tool_specs


ANALYZE_ALLOWED = MODE_TOOL_ALLOWLIST[CapabilityMode.ANALYZE]
CONSULT_ALLOWED = MODE_TOOL_ALLOWLIST[CapabilityMode.CONSULT]
DISPATCHER = frozenset(TOOL_SPECS)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("query_data", "query_data"),
        ("QueryData", "query_data"),
        ("loadSkill", "load_skill"),
        ("LOAD_SKILL", "load_skill"),
        ("inspect-schema", "inspect_schema"),
    ],
)
def test_normalize_tool_name(raw, expected):
    assert normalize_tool_name(raw) == expected


def test_resolve_exact_after_normalize():
    name, conf, notes, suggestions = resolve_tool_name(
        "QueryData", allowed_names=ANALYZE_ALLOWED
    )
    assert name == "query_data"
    assert conf == "normalize"
    assert suggestions == []
    assert any("Renamed" in n for n in notes)


def test_resolve_fuzzy_typo():
    name, conf, _, suggestions = resolve_tool_name(
        "query_dat", allowed_names=ANALYZE_ALLOWED
    )
    assert name == "query_data"
    assert conf == "fuzzy"
    assert suggestions == []


def test_fuzzy_typo_read_file():
    name, conf, _, _ = resolve_tool_name("read_flie", allowed_names=ANALYZE_ALLOWED)
    assert name == "read_file"
    assert conf == "fuzzy"


def test_fuzzy_typo_write_file_in_produce_mode():
    produce_allowed = MODE_TOOL_ALLOWLIST[CapabilityMode.PRODUCE]
    name, conf, _, _ = resolve_tool_name("write_fil", allowed_names=produce_allowed)
    assert name == "write_file"
    assert conf == "fuzzy"


def test_consult_does_not_repair_to_query_data():
    repair = repair_tool_call(
        "QueryData",
        {"resource": "submit_record_joined"},
        allowed_names=CONSULT_ALLOWED,
        dispatcher_keys=DISPATCHER,
    )
    assert repair.name is None
    assert "query_data" not in (repair.suggestions or [])


def test_apply_filter_alias_for_query_data():
    spec = TOOL_SPECS["query_data"]
    args, notes, missing = apply_arg_repairs(
        "query_data",
        {"resource": "x", "filter": {"op": "eq", "field": "a", "value": 1}},
        spec,
    )
    assert "where" in args
    assert "filter" not in args
    assert missing == frozenset()
    assert any("filter" in n for n in notes)


def test_apply_list_files_defaults():
    spec = TOOL_SPECS["list_files"]
    args, notes, missing = apply_arg_repairs("list_files", {}, spec)
    assert args["path"] == "."
    assert args["recursive"] is False
    assert args["limit"] == 200
    assert missing == frozenset()
    assert notes


def test_missing_required_reported():
    repair = repair_tool_call(
        "query_data",
        {},
        allowed_names=ANALYZE_ALLOWED,
        dispatcher_keys=DISPATCHER,
    )
    assert repair.name == "query_data"
    assert repair.missing_required == frozenset({"resource"})


def test_unknown_tool_suggestions():
    repair = repair_tool_call(
        "query_dat",
        {},
        allowed_names=ANALYZE_ALLOWED,
        dispatcher_keys=DISPATCHER,
    )
    assert repair.name == "query_data"
    assert repair.confidence == "fuzzy"

    repair2 = repair_tool_call(
        "totally_unknown_tool",
        {},
        allowed_names=ANALYZE_ALLOWED,
        dispatcher_keys=DISPATCHER,
    )
    assert repair2.name is None
    assert repair2.suggestions == [] or isinstance(repair2.suggestions, list)


def test_build_tool_specs_includes_core_tools():
    specs = build_tool_specs()
    for name in ("query_data", "inspect_schema", "load_skill", "list_files"):
        assert name in specs


def test_manifest_single_source_of_truth():
    from tools.definitions.manifest import MANIFEST, build_dispatcher, build_openai_tools
    from tools.definitions.registry import TOOL_DISPATCHER
    from tools.definitions.schemas import TOOLS

    names = {d.name for d in MANIFEST}
    assert len(TOOLS) == len(MANIFEST)
    assert {t["function"]["name"] for t in TOOLS} == names
    assert set(TOOL_DISPATCHER) == names
    assert set(build_dispatcher()) == names
    list_files = next(d for d in MANIFEST if d.name == "list_files")
    assert list_files.defaults["path"] == "."
    query = next(d for d in MANIFEST if d.name == "query_data")
    assert query.arg_aliases.get("filter") == "where"
    assert "filter" not in (query.parameters.get("properties") or {})
    resource_enum = query.parameters["properties"]["resource"].get("enum")
    assert resource_enum and "submit_record" in resource_enum
    assert "submit_record_joined" not in resource_enum
    inspect = next(d for d in MANIFEST if d.name == "inspect_schema")
    assert "Do NOT" in inspect.description or "Do NOT use" in inspect.description
    load_skill = next(d for d in MANIFEST if d.name == "load_skill")
    assert load_skill.parameters["properties"]["name"].get("enum")

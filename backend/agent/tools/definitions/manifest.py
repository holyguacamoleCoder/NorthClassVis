"""Single source of truth for agent tool metadata (schema, dispatch, repair specs)."""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Callable

from data.registry import get_registry_defaults, list_agent_resource_ids

from ..handlers.base_tool import run_edit_file, run_list_files, run_read_file, run_write_file
from ..handlers.compact import run_compact
from ..handlers.context_tools import run_build_visual_links, run_get_current_filter_context
from ..handlers.data_tools import (
    run_aggregate_data,
    run_inspect_schema,
    run_list_datasets,
    run_query_data,
    run_resolve_dataset_binding,
)
from ..handlers.load_skill import run_load_skill
from ..handlers.save_memory import run_save_memory
from ..handlers.todo_write import run_todo_write

# --- Shared parameter fragments (registry / skills → enum; reused across data tools) ---

_PERMISSION_POLICY_NOTE = (
    "Paths outside policy are denied by permission (not a tool Error). "
    "Academic CSV/tables: use inspect_schema / query_data, not read_file / list_files for analysis."
)
_READ_PATH_DOC = (
    "Relative to data/. Allowed prefixes: meta/, reports/, exports/. "
    "Forbidden: Data_*.csv, Data_SubmitRecord/, .agent, hidden segments. "
    + _PERMISSION_POLICY_NOTE
)
_WRITABLE_PATH_DOC = (
    "Relative to data/. Writable only under reports/ or exports/ (any depth). "
    "Examples: reports/academic_analysis_Class1.md, exports/quick_test.txt. "
    "Forbidden: Data_*.csv, raw datasets, .agent. "
    "In produce: writes under reports/exports usually run immediately; other paths may need user approval. "
    + _PERMISSION_POLICY_NOTE
)
_LIST_PATH_DOC = (
    "Relative to data/ workspace root. Examples: ., reports, exports, Data_SubmitRecord "
    "(names only—listing does not read file contents). "
    + _PERMISSION_POLICY_NOTE
)

_RESOURCE_RESOLVE_HINTS = (
    "Per-resource resolve params: "
    "submit_record requires class or classes (e.g. Class1 or ['Class1']); "
    "optional majors for major filter; "
    "week_aggregation requires classes; "
    "student_info and title_info need no class/classes."
)

_WHERE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "description": (
        "Safe filter DSL. Leaf: {op, field, value} with op in eq|in|gte|lte. "
        "Combine: {op: and, conditions: [<leaf>, ...]}. Fields must exist on the resource."
    ),
    "properties": {
        "op": {"type": "string", "enum": ["eq", "in", "gte", "lte", "and"]},
        "field": {"type": "string"},
        "value": {},
        "conditions": {
            "type": "array",
            "items": {"type": "object"},
            "description": "Required when op is and.",
        },
    },
}

_AGGREGATE_INPUT_SCHEMA: dict[str, Any] = {
    "oneOf": [
        {
            "type": "object",
            "properties": {
                "result_ref": {
                    "type": "string",
                    "description": "From prior query_data meta.result_ref.",
                },
                "dataset_id": {
                    "type": "string",
                    "description": "From meta.dataset_id; allows cross-turn reuse when intentional.",
                },
                "chain_from_dataset_id": {
                    "type": "string",
                    "description": "Explicit chain: aggregate this dataset from a prior query.",
                },
            },
            "anyOf": [
                {"required": ["result_ref"]},
                {"required": ["dataset_id"]},
                {"required": ["chain_from_dataset_id"]},
            ],
        },
        {
            "type": "object",
            "properties": {
                "schema": {"type": "array", "items": {"type": "object"}},
                "rows": {"type": "array", "items": {"type": "object"}},
            },
            "required": ["schema", "rows"],
            "description": "Small inline tables only; prefer result_ref for large results.",
        },
    ],
    "description": (
        "Prior query output. Prefer dataset_id or result_ref from the current turn's query_data. "
        "Use chain_from_dataset_id to continue a slice; omit limit and re-query for class-wide stats."
    ),
}


@lru_cache(maxsize=1)
def _cached_resource_ids() -> tuple[str, ...]:
    return tuple(list_agent_resource_ids())


@lru_cache(maxsize=1)
def _cached_max_query_rows() -> int:
    defaults = get_registry_defaults()
    limits = defaults.get("limits") or {}
    return int(limits.get("max_rows", 5000))


def _resource_property(*, include_enum: bool = True) -> dict[str, Any]:
    props: dict[str, Any] = {
        "type": "string",
        "description": _RESOURCE_RESOLVE_HINTS,
    }
    if include_enum:
        ids = _cached_resource_ids()
        if ids:
            props["enum"] = list(ids)
    return props


def _skill_name_property() -> dict[str, Any]:
    from skills import get_registry

    names = sorted(get_registry().documents.keys())
    prop: dict[str, Any] = {
        "type": "string",
        "description": (
            "Skill id from the catalog in the system prompt. "
            "If already loaded this session, the tool returns a short reminder instead of reloading."
        ),
    }
    if names:
        prop["enum"] = names
    return prop


def _where_property() -> dict[str, Any]:
    return dict(_WHERE_SCHEMA)


def _aggregate_input_property() -> dict[str, Any]:
    return dict(_AGGREGATE_INPUT_SCHEMA)


_MAX_QUERY_ROWS = _cached_max_query_rows()
_PREVIEW_ROWS = 50
_MAX_TODO_ITEMS = 12

# Repair: global argument aliases (all tools).
GLOBAL_ARG_ALIASES: dict[str, str] = {
    "file_path": "path",
    "filepath": "path",
    "file": "path",
    "skill_name": "name",
    "skill": "name",
}

CONCURRENCY_LIMIT = 10
CONCURRENCY_SAFE_TOOL = frozenset({
    "read_file",
    "list_files",
    "inspect_schema",
    "list_datasets",
    "resolve_dataset_binding",
    "query_data",
    "aggregate_data",
    "get_current_filter_context",
    "build_visual_links",
})
CONCURRENCY_UNSAFE_TOOL = frozenset({"write_file", "edit_file"})


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: Callable[..., str]
    defaults: dict[str, Any] = field(default_factory=dict)
    arg_aliases: dict[str, str] = field(default_factory=dict)
    pass_through_kwargs: bool = False

    def openai_tool(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    def required_params(self) -> frozenset[str]:
        req = self.parameters.get("required") or []
        return frozenset(str(k) for k in req if isinstance(k, str))

    def property_names(self) -> frozenset[str]:
        props = self.parameters.get("properties") or {}
        return frozenset(str(k) for k in props.keys())


def _make_dispatcher(defn: ToolDefinition) -> Callable[..., str]:
    if defn.pass_through_kwargs:
        return lambda **kwargs: defn.handler(**kwargs)

    keys = defn.property_names()

    def wrapper(**kwargs: Any) -> str:
        merged = {**defn.defaults, **kwargs}
        bound = {k: merged[k] for k in keys if k in merged}
        return defn.handler(**bound)

    return wrapper


# --- Parameter schemas (OpenAI function.parameters) ---

_READ_FILE_PARAMS = {
    "type": "object",
    "properties": {
        "path": {
            "type": "string",
            "description": _READ_PATH_DOC + " Examples: meta/data_catalog.md, reports/academic_analysis_Class1.md.",
        },
        "limit": {
            "type": "integer",
            "minimum": 1,
            "maximum": 5000,
            "description": "Max lines to return. Omitting limit may still truncate output at ~50000 characters.",
        },
    },
    "required": ["path"],
}

_LIST_FILES_PARAMS = {
    "type": "object",
    "properties": {
        "path": {
            "type": "string",
            "description": _LIST_PATH_DOC + " Default when omitted: . (data workspace root).",
        },
        "recursive": {
            "type": "boolean",
            "description": (
                "When true, walks subdirectories. Prefer a narrow path; large trees are truncated by limit."
            ),
        },
        "limit": {
            "type": "integer",
            "minimum": 1,
            "maximum": 500,
            "description": "Max entries to list. Default 200 when omitted (via runtime defaults).",
        },
    },
}

_WRITE_FILE_PARAMS = {
    "type": "object",
    "properties": {
        "path": {"type": "string", "description": _WRITABLE_PATH_DOC},
        "content": {
            "type": "string",
            "description": (
                "UTF-8 text (markdown recommended for reports); newlines normalized to LF on write."
            ),
        },
    },
    "required": ["path", "content"],
}

_EDIT_FILE_PARAMS = {
    "type": "object",
    "properties": {
        "path": {"type": "string", "description": _WRITABLE_PATH_DOC},
        "old_text": {
            "type": "string",
            "description": "Exact UTF-8 substring to replace (first occurrence only).",
        },
        "new_text": {"type": "string"},
    },
    "required": ["path", "old_text", "new_text"],
}

_TODO_WRITE_PARAMS = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "maxItems": _MAX_TODO_ITEMS,
            "description": (
                f"Session plan steps (recommended ≤5, max {_MAX_TODO_ITEMS}). "
                "Exactly one item may be in_progress; active_form only applies to that item. "
                "Empty list clears the plan."
            ),
            "items": {
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "Step label; prefer inspect_schema/query_data wording, not read CSV.",
                    },
                    "status": {
                        "type": "string",
                        "enum": ["pending", "in_progress", "completed"],
                    },
                    "active_form": {
                        "type": "string",
                        "description": "Optional present-continuous label (in_progress only).",
                    },
                    "acceptance": {
                        "type": "string",
                        "description": (
                            "Verifiable done criteria (e.g. count_distinct student_ID by major, full scan)."
                        ),
                    },
                },
                "required": ["content", "status"],
            },
        },
    },
    "required": ["items"],
}

_COMPACT_PARAMS = {
    "type": "object",
    "properties": {
        "focus": {
            "type": "string",
            "description": (
                "Optional goal to preserve in the macro summary, e.g. "
                "'Class1 score analysis, keep result_ref abc123'."
            ),
        },
    },
}

_LOAD_SKILL_PARAMS = {
    "type": "object",
    "properties": {
        "name": _skill_name_property(),
    },
    "required": ["name"],
}

_SAVE_MEMORY_PARAMS = {
    "type": "object",
    "properties": {
        "name": {
            "type": "string",
            "description": (
                "Short id [a-z0-9_-] (e.g. prefer_tabs, report_style_class1). "
                "Same name overwrites the previous .memory file."
            ),
        },
        "description": {
            "type": "string",
            "description": "One-line summary of what this memory captures",
        },
        "type": {
            "type": "string",
            "enum": ["user", "feedback", "project", "reference"],
            "description": (
                "user=teacher preferences; feedback=corrections to analysis; "
                "project=non-obvious conventions; reference=external links/paths"
            ),
        },
        "content": {
            "type": "string",
            "description": "Full memory body (one topic per save; multi-line OK).",
        },
    },
    "required": ["name", "description", "type", "content"],
}

_LIST_DATASETS_PARAMS = {
    "type": "object",
    "properties": {
        "tail": {
            "type": "integer",
            "minimum": 1,
            "maximum": 50,
            "description": "Max datasets to return (newest first). Default 20.",
        },
        "user_turn": {
            "type": "integer",
            "description": "Optional filter: only datasets from this teacher question index.",
        },
    },
}

_GET_FILTER_CONTEXT_PARAMS = {
    "type": "object",
    "properties": {},
}

_BUILD_VISUAL_LINKS_PARAMS = {
    "type": "object",
    "properties": {
        "links": {
            "type": "array",
            "description": (
                "Candidate navigation links. Each item: {view, params [, label]}. "
                "Views must match visual_link_contract.yaml (WeekView, QuestionView, "
                "StudentView, PortraitView, ScatterView)."
            ),
            "items": {
                "type": "object",
                "properties": {
                    "view": {"type": "string"},
                    "params": {"type": "object"},
                    "label": {"type": "string"},
                },
                "required": ["view", "params"],
            },
        },
        "archetype": {
            "type": "string",
            "enum": [
                "trend_decline",
                "knowledge_weakness",
                "student_diagnosis",
                "class_overview",
            ],
            "description": (
                "Optional question archetype; missing recommended views yield warnings only."
            ),
        },
    },
    "required": ["links"],
}

_INSPECT_SCHEMA_PARAMS = {
    "type": "object",
    "properties": {
        "resource": _resource_property(),
        "class": {
            "type": "string",
            "description": "Single class for submit_record (e.g. Class1); alias of classes=[...].",
        },
        "classes": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Class list for submit_record or week_aggregation.",
        },
        "majors": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Optional major filter on submit_record or week_aggregation.",
        },
    },
    "required": ["resource"],
}

_QUERY_DATA_PARAMS = {
    "type": "object",
    "properties": {
        "resource": _resource_property(),
        "select": {"type": "array", "items": {"type": "string"}},
        "where": _where_property(),
        "group_by": {"type": "array", "items": {"type": "string"}},
        "order_by": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "field": {"type": "string"},
                    "dir": {"type": "string", "enum": ["asc", "desc"]},
                },
            },
        },
        "limit": {
            "type": "integer",
            "minimum": 1,
            "maximum": _MAX_QUERY_ROWS,
            "description": (
                f"Optional cap on rows scanned (1–{_MAX_QUERY_ROWS}). "
                f"Omit limit for full matching set (required for correct count/mean). "
                f"Do NOT use limit:0 (auto-normalized to full scan). Preview ~{_PREVIEW_ROWS} rows; "
                f"full data via meta.result_ref when truncated."
            ),
        },
        "class": {
            "type": "string",
            "description": "Single class for submit_record (e.g. Class1); alias of classes=[...].",
        },
        "classes": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Class list for submit_record or week_aggregation.",
        },
        "majors": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Optional major filter on submit_record or week_aggregation.",
        },
    },
    "required": ["resource"],
}

_AGGREGATE_DATA_PARAMS = {
    "type": "object",
    "properties": {
        "input": _aggregate_input_property(),
        "metrics": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "op": {
                        "type": "string",
                        "enum": ["count", "count_distinct", "sum", "mean", "min", "max"],
                    },
                    "field": {
                        "type": "string",
                        "description": (
                            "Required for mean/sum/min/max/count_distinct; optional for count. "
                            "Use count_distinct on student_ID for enrollment (not count)."
                        ),
                    },
                    "as": {"type": "string"},
                },
                "required": ["op"],
            },
            "description": (
                "Example: [{\"op\":\"count_distinct\",\"field\":\"student_ID\",\"as\":\"students\"}, "
                "{\"op\":\"mean\",\"field\":\"score\",\"as\":\"avg\"}]. count=rows; count_distinct=unique values."
            ),
        },
        "dimensions": {"type": "array", "items": {"type": "string"}},
        "window": {
            "type": "object",
            "properties": {
                "field": {"type": "string"},
                "size": {"type": "integer"},
            },
        },
        "resource": {
            **_resource_property(),
            "description": (
                "Optional when using inline input, or when the runtime auto-runs a preparatory "
                "query (resource + metrics without input). Prefer explicit query_data first."
            ),
        },
        "bind": {
            "type": "string",
            "enum": ["auto", "chain", "fresh"],
            "description": (
                "Binding intent: chain=slice/top-N follow-up; fresh=class-wide/new scope; "
                "auto=infer from metrics (default)."
            ),
        },
    },
    "required": ["input", "metrics"],
}

_RESOLVE_BINDING_PARAMS = {
    "type": "object",
    "properties": {
        "input": _aggregate_input_property(),
        "metrics": _AGGREGATE_DATA_PARAMS["properties"]["metrics"],
        "bind": _AGGREGATE_DATA_PARAMS["properties"]["bind"],
    },
}


MANIFEST: tuple[ToolDefinition, ...] = (
    # File/Base Tools
    ToolDefinition(
        name="read_file",
        description=(
            "Read UTF-8 text under data/ (analyze or produce only; unavailable in consult). "
            "Use when: report drafts, meta/data_catalog.md, small exports, or verifying a path cited in a report. "
            "Do NOT use for: Data_*.csv or Data_SubmitRecord/ (inspect_schema / query_data); "
            "opening files after list_files on academic CSV paths (listing is not reading); "
            "statistics or tables (query_data); binary/non-UTF-8/huge files. "
            "Returns a status line then content; may truncate at ~50000 chars or use persisted-output preview."
        ),
        parameters=_READ_FILE_PARAMS,
        handler=run_read_file,
    ),
    ToolDefinition(
        name="list_files",
        description=(
            "List file and directory names under the data/ workspace root (consult, analyze, produce). "
            "Use when: unsure what exists under reports/ or exports/; consult-mode directory browse "
            "(names only, not file contents). "
            "Do NOT use for: CSV column names or sample rows (inspect_schema); row counts or stats "
            "(query_data in analyze); logical resources (resource_registry + inspect_schema). "
            "Listing Data_SubmitRecord/*.csv filenames does not read CSV—switch to analyze, then "
            "inspect_schema(resource=submit_record, class=Class1). "
            "Defaults: path=. , limit=200. Returns [List: root=…, count=…, truncated=…] then paths."
        ),
        parameters=_LIST_FILES_PARAMS,
        handler=run_list_files,
        defaults={"path": ".", "recursive": False, "limit": 200},
    ),
    ToolDefinition(
        name="write_file",
        description=(
            "Create or overwrite a UTF-8 file (produce mode only; denied in analyze/consult). "
            "Use when: saving a deliverable report (reports/*.md) or export artifact (exports/*) "
            "after analysis; user asked to persist conclusions. "
            "Do NOT use for: Data_*.csv, raw datasets, .agent; structured tables (query_data, "
            "then write a summary). "
            "Writable: reports/** and exports/** (usually auto-allowed); other paths under data/ "
            "may trigger permission ask. Returns [Write OK: path, bytes, created|overwritten]."
        ),
        parameters=_WRITE_FILE_PARAMS,
        handler=run_write_file,
    ),
    ToolDefinition(
        name="edit_file",
        description=(
            "Replace the first exact UTF-8 match of old_text (produce mode only). "
            "Use when: small section updates in an existing reports/ draft (unique old_text). "
            "Do NOT use for: whole-file rewrites (write_file); Data_*.csv; analyze/consult; "
            "retrying without read_file after Text not found. "
            "Same path/approval rules as write_file. Returns [Edit OK: path]."
        ),
        parameters=_EDIT_FILE_PARAMS,
        handler=run_edit_file,
    ),

    # Session Tools
    ToolDefinition(
        name="todo_write",
        description=(
            "Rewrite the in-session analysis plan (analyze or produce only; not in consult). "
            "Use when: ≥3 steps across multiple tool rounds (inspect→query→aggregate→report); "
            "starting a multi-class or cross-resource task; after each data step, update statuses. "
            "Each item should include acceptance (how to verify done). "
            "After query_data/aggregate_data, mark steps completed when meta has no warnings. "
            "Do NOT use for: single-turn answers; one query_data that suffices; substituting "
            "query/aggregate; more than 12 items. "
            "Rules: at most one in_progress; runtime reminds if data returns without todo update. "
            "When a step needs data, name inspect_schema/query_data—not read_file on CSV."
        ),
        parameters=_TODO_WRITE_PARAMS,
        handler=run_todo_write,
    ),
    ToolDefinition(
        name="compact",
        description=(
            "Manually trigger macro context compression (analyze or produce only). "
            "Use when: context is very long, repeated tool errors, or the teacher asks to summarize and continue. "
            "Optional focus keeps the current goal in the summary. "
            "Do NOT use right after a critical query_data/aggregate_data result unless still over budget—"
            "run aggregate or write findings first; confirm key meta.result_ref is used. "
            "Do NOT use every turn: the loop already micro-compacts each turn and may auto-macro compact. "
            "Cannot replace query_data for shrinking tables. "
            "Side effect: AgentLoop rewrites message history after this call; the tool return reports stats."
        ),
        parameters=_COMPACT_PARAMS,
        handler=run_compact,
    ),
    ToolDefinition(
        name="load_skill",
        description=(
            "Load full SKILL.md instructions for a fixed workflow (e.g. report template, SOP). "
            "Use when: the task explicitly needs steps from a named skill in the system prompt. "
            "Do NOT use to discover table columns (inspect_schema) or run statistics (query_data); "
            "do not reload a skill already loaded this session (tool returns a reminder); "
            "if the system prompt already summarizes the skill, query first, load only if stuck. "
            "Table structure → inspect_schema; numbers → query_data / aggregate_data."
        ),
        parameters=_LOAD_SKILL_PARAMS,
        handler=run_load_skill,
        pass_through_kwargs=True,
    ),
    ToolDefinition(
        name="save_memory",
        description=(
            "Save cross-session memory to .memory/ (analyze or produce only). "
            "Use when: explicit teacher preferences (report format, default class); corrections to "
            "methodology; project conventions not in catalog; external doc/system links. "
            "Types: user | feedback | project | reference. "
            "Do NOT save: CSV column layouts, field lists, or stats (use inspect_schema/query_data/reports); "
            "current-session TODO/progress; secrets or credentials. "
            "Analysis conclusions belong in reports; memories are preferences and conventions. "
            "Same name overwrites prior file; saved content appears in future system prompts."
        ),
        parameters=_SAVE_MEMORY_PARAMS,
        handler=run_save_memory,
    ),

    # Adapter Tools (Phase 3 — nav context + visual link validation)
    ToolDefinition(
        name="get_current_filter_context",
        description=(
            "Return the current analysis scope (classes, majors, week_range, selected students). "
            "Use when: multi-class or week-range questions; confirming Nav scope before query_data; "
            "consult mode scope introspection. "
            "Does NOT compute metrics or query tables. "
            "Nav scope is also auto-applied to query_data/inspect_schema when classes/majors are omitted."
        ),
        parameters=_GET_FILTER_CONTEXT_PARAMS,
        handler=run_get_current_filter_context,
        pass_through_kwargs=True,
    ),
    ToolDefinition(
        name="build_visual_links",
        description=(
            "Validate and normalize frontend visual navigation links per visual_link_contract.yaml. "
            "Use after analysis when suggesting chart/student/knowledge drill-downs. "
            "WeekView: ONE link only; include week_range; student diagnosis MUST include "
            "student_ids with exactly the target student; class reports should pass 2–3 representative "
            "student_ids—never omit student_ids (embedded chart would be empty). "
            "QuestionView: prefer title_ids (1–5). StudentView: student_ids required. "
            "Omit kind unless one cluster—never three WeekView links for kind 1/2/3. "
            "Does NOT render charts or write business conclusions. "
            "Returns visual_links, warnings, and rejected items."
        ),
        parameters=_BUILD_VISUAL_LINKS_PARAMS,
        handler=run_build_visual_links,
    ),

    # Data Tools
    ToolDefinition(
        name="list_datasets",
        description=(
            "List query_data results registered in this session (dataset_id, result_ref, "
            "row counts, limit, user_turn). Use when: you need a dataset_id for aggregate_data "
            "or chain_from_dataset_id; binding failed and you forgot which ref to use; "
            "reusing a prior slice across turns (pass dataset_id explicitly). "
            "Do NOT use for: raw CSV; column discovery (inspect_schema); running statistics "
            "(aggregate_data). Returns JSON with datasets newest-first and meta.next_step hints."
        ),
        parameters=_LIST_DATASETS_PARAMS,
        handler=run_list_datasets,
        pass_through_kwargs=True,
    ),
    ToolDefinition(
        name="resolve_dataset_binding",
        description=(
            "Resolve which dataset_id to use for aggregate_data from the teacher question "
            "and session catalog (semantic binding). Use when: multiple query_data results "
            "exist (slice vs full class); binding error; unsure which result_ref. "
            "Returns JSON with decision.dataset_id and next_step. "
            "Runtime also runs this internally before aggregate when ambiguous."
        ),
        parameters=_RESOLVE_BINDING_PARAMS,
        handler=run_resolve_dataset_binding,
        pass_through_kwargs=True,
    ),
    ToolDefinition(
        name="inspect_schema",
        description=(
            "Inspect a logical resource: columns, types, sample rows, row count estimate. "
            "Returns column metadata JSON (not TabularResult / no meta.result_ref). "
            "Use when: first time analyzing a resource; unsure of column or join keys; "
            "confirming submit_record needs class or classes. "
            "Use before query_data on an unfamiliar resource. "
            "Do NOT use for: counts, means, grouping, or rankings (query_data / aggregate_data); "
            "re-inspecting the same resource in one task; reading full catalog text (read_file meta/ in analyze); raw CSV via read_file. "
            "In consult mode: structure only—no statistics; for class averages or counts, "
            "ask to switch to analyze mode."
        ),
        parameters=_INSPECT_SCHEMA_PARAMS,
        handler=run_inspect_schema,
        pass_through_kwargs=True,
    ),
    ToolDefinition(
        name="query_data",
        description=(
            "Primary analysis tool: filter, project, group, sort, and limit logical resources. "
            "Use when: class comparisons, student filters, sorted previews, or sampling before export. "
            "Example: submit_record with class='Class1' or classes=['Class1']; majors=['J23517'] for major filter. "
            "Returns TabularResult JSON (preview rows ~50; full data in meta.result_ref when truncated). "
            "Do NOT use for: column discovery only (inspect_schema); consult mode (tool unavailable); "
            "repeating the same query; filtering student_ID with major codes like J23517 (use majors or where.major); "
            "reading Data_*.csv via read_file. "
            "After success, use meta.result_ref with aggregate_data when you need metrics."
        ),
        parameters=_QUERY_DATA_PARAMS,
        handler=run_query_data,
        arg_aliases={"filter": "where"},
        pass_through_kwargs=True,
    ),
    ToolDefinition(
        name="aggregate_data",
        description=(
            "Aggregate metrics on a prior query result (count, mean, min, max, sum) with optional "
            "grouping by dimensions. Use after query_data when you need rollups, not instead of query. "
            "Returns TabularResult JSON; meta.auto_input when runtime bound input; "
            "use bind=chain|fresh or input.dataset_id for explicit chaining. "
            "Do NOT use for: raw CSV; replacing query_data; calling with only resource+metrics unless "
            "you accept an implicit preparatory query (prefer explicit query_data first). "
            "Required: input (result_ref or small inline rows) and metrics."
        ),
        parameters=_AGGREGATE_DATA_PARAMS,
        handler=run_aggregate_data,
        pass_through_kwargs=True,
    ),
)

MANIFEST_BY_NAME: dict[str, ToolDefinition] = {d.name: d for d in MANIFEST}


def build_openai_tools() -> list[dict[str, Any]]:
    return [d.openai_tool() for d in MANIFEST]


def build_dispatcher() -> dict[str, Callable[..., str]]:
    return {d.name: _make_dispatcher(d) for d in MANIFEST}


def build_repair_defaults() -> dict[str, dict[str, Any]]:
    return {d.name: dict(d.defaults) for d in MANIFEST if d.defaults}


def build_per_tool_arg_aliases() -> dict[str, dict[str, str]]:
    return {d.name: dict(d.arg_aliases) for d in MANIFEST if d.arg_aliases}

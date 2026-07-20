"""Scenario schema for the agent benchmark harness."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ExpectAggregate:
    turn_index: int
    expect: str
    ordinal: int | None = None
    expect_error: bool = False
    accept_guard_error: bool = False
    note: str | None = None


@dataclass
class ExpectTools:
    turn_index: int | None = None
    names: list[str] = field(default_factory=list)
    any_of: list[str] = field(default_factory=list)
    min_count: int | None = None


@dataclass
class ExpectArg:
    tool: str
    path: str
    turn_index: int | None = None
    ordinal: int | None = None
    eq: Any = None
    gte: Any = None
    lte: Any = None
    contains: Any = None
    exists: bool | None = None


@dataclass
class ExpectTaskAssert:
    kind: str
    tool: str | None = None
    metric_op: str | None = None
    field: str | None = None
    path: str | None = None
    op: str | None = None
    value: Any = None
    turn_index: int | None = None


@dataclass
class ExpectTask:
    asserts: list[ExpectTaskAssert] = field(default_factory=list)
    note: str | None = None


@dataclass
class ExpectScope:
    """Declarative checks that injected scope appears in the LLM user content."""

    must_contain: list[str] = field(default_factory=list)
    must_call_tools: list[str] = field(default_factory=list)
    hard: bool = False  # soft by default; set true only for smoke that must gate


@dataclass
class Scenario:
    id: str
    tags: list[str] = field(default_factory=list)
    mode: str = "analyze"
    filter_context: dict[str, Any] = field(default_factory=dict)
    ui_scope: dict[str, Any] | None = None
    turns: list[str] = field(default_factory=list)
    expect_aggregates: list[ExpectAggregate] = field(default_factory=list)
    expect_tools: list[ExpectTools] = field(default_factory=list)
    forbid_tools: list[str] = field(default_factory=list)
    expect_args: list[ExpectArg] = field(default_factory=list)
    expect_task: ExpectTask | None = None
    expect_error: bool = False
    expect_scope: ExpectScope | None = None
    expect_max_turns: int | None = None
    expect_max_tool_calls: int | None = None
    enabled: bool = True
    note: str | None = None

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.id:
            errors.append("missing id")
        if not self.turns:
            errors.append(f"{self.id}: turns must be non-empty")
        if len(self.turns) > 3:
            errors.append(f"{self.id}: turns exceed hard limit 3 (got {len(self.turns)})")
        if self.expect_max_turns is not None and self.expect_max_turns < len(self.turns):
            errors.append(
                f"{self.id}: expect_max_turns={self.expect_max_turns} < len(turns)={len(self.turns)}"
            )
        return errors


def _parse_expect_aggregates(raw: list[dict[str, Any]] | None) -> list[ExpectAggregate]:
    out: list[ExpectAggregate] = []
    for e in raw or []:
        out.append(
            ExpectAggregate(
                turn_index=int(e["turn_index"]),
                expect=str(e["expect"]),
                ordinal=int(e["ordinal"]) if e.get("ordinal") is not None else None,
                expect_error=bool(e.get("expect_error")),
                accept_guard_error=bool(e.get("accept_guard_error")),
                note=e.get("note"),
            )
        )
    return out


def _parse_expect_tools(raw: list[dict[str, Any]] | str | None) -> list[ExpectTools]:
    if raw is None:
        return []
    if isinstance(raw, list) and raw and isinstance(raw[0], str):
        return [ExpectTools(names=[str(x) for x in raw])]
    out: list[ExpectTools] = []
    for e in raw or []:
        if isinstance(e, str):
            out.append(ExpectTools(names=[e]))
            continue
        out.append(
            ExpectTools(
                turn_index=int(e["turn_index"]) if e.get("turn_index") is not None else None,
                names=[str(x) for x in (e.get("names") or [])],
                any_of=[str(x) for x in (e.get("any_of") or [])],
                min_count=int(e["min_count"]) if e.get("min_count") is not None else None,
            )
        )
    return out


def _parse_expect_args(raw: list[dict[str, Any]] | None) -> list[ExpectArg]:
    out: list[ExpectArg] = []
    for e in raw or []:
        out.append(
            ExpectArg(
                tool=str(e["tool"]),
                path=str(e["path"]),
                turn_index=int(e["turn_index"]) if e.get("turn_index") is not None else None,
                ordinal=int(e["ordinal"]) if e.get("ordinal") is not None else None,
                eq=e.get("eq"),
                gte=e.get("gte"),
                lte=e.get("lte"),
                contains=e.get("contains"),
                exists=e.get("exists"),
            )
        )
    return out


def _parse_expect_task(raw: dict[str, Any] | None) -> ExpectTask | None:
    if not raw:
        return None
    asserts: list[ExpectTaskAssert] = []
    for a in raw.get("asserts") or []:
        asserts.append(
            ExpectTaskAssert(
                kind=str(a["kind"]),
                tool=a.get("tool"),
                metric_op=a.get("metric_op"),
                field=a.get("field"),
                path=a.get("path"),
                op=a.get("op"),
                value=a.get("value"),
                turn_index=int(a["turn_index"]) if a.get("turn_index") is not None else None,
            )
        )
    return ExpectTask(asserts=asserts, note=raw.get("note"))


def _parse_expect_scope(raw: dict[str, Any] | None) -> ExpectScope | None:
    if not raw:
        return None
    return ExpectScope(
        must_contain=[str(x) for x in (raw.get("must_contain") or [])],
        must_call_tools=[str(x) for x in (raw.get("must_call_tools") or [])],
        hard=bool(raw.get("hard")),
    )


_ENTITY_REF = "$entity."
_DEFAULT_EXCLUDE_TAGS = frozenset({"scope-extended"})


def load_entities(path: Path | None = None) -> dict[str, Any]:
    fp = path or (Path(__file__).resolve().parent / "fixtures" / "entities.json")
    if not fp.is_file():
        return {}
    raw = json.loads(fp.read_text(encoding="utf-8"))
    return raw if isinstance(raw, dict) else {}


def _entity_lookup(entities: dict[str, Any], ref: str) -> Any:
    """Resolve `$entity.foo` / `$entity.foo.0` against entities.json."""
    if not isinstance(ref, str) or not ref.startswith(_ENTITY_REF):
        return ref
    path = ref[len(_ENTITY_REF) :]
    cur: Any = entities
    for part in path.split("."):
        if isinstance(cur, dict):
            if part not in cur:
                raise KeyError(f"entities missing key path {ref!r}")
            cur = cur[part]
        elif isinstance(cur, list):
            cur = cur[int(part)]
        else:
            raise KeyError(f"cannot resolve {ref!r}")
    return cur


def _substitute_entities(value: Any, entities: dict[str, Any]) -> Any:
    if isinstance(value, str):
        if value.startswith(_ENTITY_REF) and " " not in value:
            return _entity_lookup(entities, value)
        if _ENTITY_REF in value:
            out = value
            refs: list[str] = []
            i = 0
            while True:
                j = out.find(_ENTITY_REF, i)
                if j < 0:
                    break
                k = j + len(_ENTITY_REF)
                while k < len(out) and (out[k].isalnum() or out[k] in "._"):
                    k += 1
                refs.append(out[j:k])
                i = k
            for ref in sorted(set(refs), key=len, reverse=True):
                resolved = _entity_lookup(entities, ref)
                out = out.replace(ref, str(resolved))
            return out
        return value
    if isinstance(value, list):
        if len(value) == 1 and isinstance(value[0], str) and value[0].startswith(_ENTITY_REF):
            resolved = _entity_lookup(entities, value[0])
            return list(resolved) if isinstance(resolved, (list, tuple)) else [resolved]
        return [_substitute_entities(v, entities) for v in value]
    if isinstance(value, dict):
        return {k: _substitute_entities(v, entities) for k, v in value.items()}
    return value


def parse_scenario(item: dict[str, Any], *, entities: dict[str, Any] | None = None) -> Scenario:
    ents = entities if entities is not None else {}
    raw = _substitute_entities(dict(item), ents)
    forbid = raw.get("forbid_tools") or []
    if isinstance(forbid, str):
        forbid = [forbid]
    ui_scope = dict(raw["ui_scope"]) if isinstance(raw.get("ui_scope"), dict) else None
    filter_context = dict(raw.get("filter_context") or {})
    # Keep session FC aligned with composer student selection.
    if ui_scope and ui_scope.get("selected_student_ids") and not filter_context.get(
        "selected_student_ids"
    ):
        filter_context["selected_student_ids"] = list(ui_scope["selected_student_ids"])
    return Scenario(
        id=str(raw["id"]),
        tags=[str(t) for t in (raw.get("tags") or [])],
        mode=str(raw.get("mode") or "analyze"),
        filter_context=filter_context,
        ui_scope=ui_scope,
        turns=[str(t) for t in (raw.get("turns") or [])],
        expect_aggregates=_parse_expect_aggregates(raw.get("expect_aggregates")),
        expect_tools=_parse_expect_tools(raw.get("expect_tools")),
        forbid_tools=[str(x) for x in forbid],
        expect_args=_parse_expect_args(raw.get("expect_args")),
        expect_task=_parse_expect_task(raw.get("expect_task")),
        expect_error=bool(raw.get("expect_error")),
        expect_scope=_parse_expect_scope(raw.get("expect_scope")),
        expect_max_turns=int(raw["expect_max_turns"]) if raw.get("expect_max_turns") is not None else None,
        expect_max_tool_calls=(
            int(raw["expect_max_tool_calls"]) if raw.get("expect_max_tool_calls") is not None else None
        ),
        enabled=bool(raw.get("enabled", True)),
        note=raw.get("note"),
    )


def load_scenarios_file(path: Path, *, entities: dict[str, Any] | None = None) -> list[Scenario]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError(f"scenario file must be a JSON array: {path}")
    ents = entities if entities is not None else load_entities()
    return [parse_scenario(item, entities=ents) for item in raw]


def load_scenarios(
    path: Path | None = None,
    *,
    tags: list[str] | None = None,
    scenario_id: str | None = None,
    include_disabled: bool = False,
    include_extended: bool = False,
) -> list[Scenario]:
    """Load scenarios from a file or the default fixtures/scenarios directory."""
    entities = load_entities()
    if path is not None and path.is_file():
        scenarios = load_scenarios_file(path, entities=entities)
    elif path is not None and path.is_dir():
        scenarios = []
        for fp in sorted(path.glob("*.json")):
            scenarios.extend(load_scenarios_file(fp, entities=entities))
    else:
        default_dir = Path(__file__).resolve().parent / "fixtures" / "scenarios"
        legacy = Path(__file__).resolve().parent / "fixtures" / "binding_online_scenarios.json"
        scenarios = []
        if default_dir.is_dir():
            for fp in sorted(default_dir.glob("*.json")):
                scenarios.extend(load_scenarios_file(fp, entities=entities))
        elif legacy.is_file():
            scenarios = load_scenarios_file(legacy, entities=entities)
        else:
            raise FileNotFoundError(f"No scenarios found under {default_dir}")

    if scenario_id:
        scenarios = [s for s in scenarios if s.id == scenario_id]
    else:
        if not include_disabled:
            scenarios = [s for s in scenarios if s.enabled]
        tag_set = {t.lower() for t in (tags or [])}
        want_extended = include_extended or ("scope-extended" in tag_set)
        if not want_extended:
            scenarios = [
                s
                for s in scenarios
                if not _DEFAULT_EXCLUDE_TAGS.intersection({t.lower() for t in s.tags})
            ]
        if tags:
            scenarios = [
                s for s in scenarios if tag_set.intersection({t.lower() for t in s.tags})
            ]

    seen: set[str] = set()
    unique: list[Scenario] = []
    for s in scenarios:
        if s.id in seen:
            continue
        seen.add(s.id)
        unique.append(s)
    return unique


def validate_scenarios(scenarios: list[Scenario]) -> list[str]:
    errors: list[str] = []
    ids: set[str] = set()
    for s in scenarios:
        errors.extend(s.validate())
        if s.id in ids:
            errors.append(f"duplicate scenario id: {s.id}")
        ids.add(s.id)
    return errors

"""Normalize and repair LLM tool names/arguments before dispatch."""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field
from typing import Any

from .specs import TOOL_SPECS, ToolSpec

GLOBAL_ARG_ALIASES: dict[str, str] = {
    "file_path": "path",
    "filepath": "path",
    "file": "path",
    "skill_name": "name",
    "skill": "name",
}

PER_TOOL_ARG_ALIASES: dict[str, dict[str, str]] = {
    "query_data": {"filter": "where"},
}

FUZZY_CUTOFF = 0.75
FUZZY_MIN_RATIO = 0.88


@dataclass
class ToolRepairResult:
    name: str | None
    args: dict[str, Any]
    notes: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    confidence: str | None = None
    missing_required: frozenset[str] = field(default_factory=frozenset)
    original_name: str | None = None

    @property
    def was_repaired(self) -> bool:
        return bool(self.notes)


def normalize_tool_name(raw: str | None) -> str:
    s = (raw or "").strip()
    if not s:
        return ""
    s = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", s)
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s)
    return s.lower().replace("-", "_")


def _safe_fuzzy_match(norm: str, candidate: str) -> bool:
    if ("read" in norm and "write" in candidate) or (
        "write" in norm and "read" in candidate
    ):
        return False
    return difflib.SequenceMatcher(None, norm, candidate).ratio() >= FUZZY_MIN_RATIO


def resolve_tool_name(
    raw: str | None,
    *,
    allowed_names: frozenset[str],
) -> tuple[str | None, str | None, list[str], list[str]]:
    notes: list[str] = []
    original = (raw or "").strip() or None
    if not original:
        return None, None, notes, []

    norm = normalize_tool_name(original)
    if not norm:
        return None, None, notes, []

    if norm in allowed_names:
        if norm != original:
            notes.append(f"[Tool repair] Renamed tool {original!r} -> {norm!r}")
        return norm, "normalize", notes, []

    by_lower = {n.lower(): n for n in allowed_names}
    if norm in by_lower:
        canon = by_lower[norm]
        notes.append(f"[Tool repair] Matched tool {original!r} -> {canon!r} (case)")
        return canon, "case", notes, []

    candidates = difflib.get_close_matches(
        norm, sorted(allowed_names), n=3, cutoff=FUZZY_CUTOFF
    )
    if len(candidates) == 1 and _safe_fuzzy_match(norm, candidates[0]):
        canon = candidates[0]
        notes.append(f"[Tool repair] Fuzzy matched tool {original!r} -> {canon!r}")
        return canon, "fuzzy", notes, []

    return None, None, notes, candidates


def apply_arg_repairs(
    tool_name: str,
    args: dict[str, Any],
    spec: ToolSpec | None,
) -> tuple[dict[str, Any], list[str], frozenset[str]]:
    out = dict(args)
    notes: list[str] = []

    aliases = dict(GLOBAL_ARG_ALIASES)
    aliases.update(PER_TOOL_ARG_ALIASES.get(tool_name, {}))
    for wrong, right in aliases.items():
        if wrong in out and right not in out:
            out[right] = out.pop(wrong)
            notes.append(f"[Tool repair] Arg {wrong!r} -> {right!r}")

    if spec is not None:
        for key, val in spec.defaults.items():
            if key not in out:
                out[key] = val
                notes.append(f"[Tool repair] Default {key}={val!r}")

    missing: frozenset[str] = frozenset()
    if spec is not None:
        missing = spec.required - frozenset(out.keys())
        if missing:
            notes.append(
                "[Tool repair] Missing required: "
                + ", ".join(sorted(missing))
            )

    return out, notes, missing


def repair_tool_call(
    tool_name: str | None,
    args: dict[str, Any] | None,
    *,
    allowed_names: frozenset[str],
    dispatcher_keys: frozenset[str] | None = None,
) -> ToolRepairResult:
    parsed_args = dict(args or {})
    original_name = (tool_name or "").strip() or None

    candidates = allowed_names
    if dispatcher_keys is not None:
        candidates = allowed_names & dispatcher_keys
    if not candidates:
        candidates = allowed_names

    canon, confidence, name_notes, suggestions = resolve_tool_name(
        original_name, allowed_names=candidates
    )
    all_notes = list(name_notes)

    if canon is None:
        return ToolRepairResult(
            name=None,
            args=parsed_args,
            notes=all_notes,
            suggestions=suggestions,
            original_name=original_name,
        )

    spec = TOOL_SPECS.get(canon)
    repaired_args, arg_notes, missing = apply_arg_repairs(canon, parsed_args, spec)
    all_notes.extend(arg_notes)

    return ToolRepairResult(
        name=canon,
        args=repaired_args,
        notes=all_notes,
        suggestions=suggestions,
        confidence=confidence,
        missing_required=missing,
        original_name=original_name,
    )

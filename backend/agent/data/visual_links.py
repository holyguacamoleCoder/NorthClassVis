from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from .filter_context import (
    FilterContext,
    _coerce_week_range,
    clean_student_ids,
    is_placeholder_student_id,
    is_valid_student_id,
    sample_typical_student_ids,
)

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_CONTRACT_PATH = _PROJECT_ROOT / "data" / "meta" / "visual_link_contract.yaml"


@lru_cache(maxsize=1)
def _load_contract_cached(path_str: str) -> dict[str, Any]:
    path = Path(path_str)
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def load_contract(contract_path: Path | None = None) -> dict[str, Any]:
    path = contract_path or _DEFAULT_CONTRACT_PATH
    return _load_contract_cached(str(path.resolve()))


def _view_enum(contract: dict[str, Any]) -> frozenset[str]:
    return frozenset(str(v) for v in (contract.get("view_enum") or []))


def _view_params_spec(contract: dict[str, Any], view: str) -> dict[str, Any]:
    specs = contract.get("view_params") or {}
    raw = specs.get(view) or {}
    return {k: v for k, v in raw.items() if isinstance(v, dict) and k != "example"}


_PLACEHOLDER_KNOWLEDGE = frozenset(
    {"some_knowledge", "某知识点", "knowledge", "unknown", "n/a", "na"}
)


def normalize_question_params(params: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    knowledge_raw = params.get("knowledge")
    knowledge = (
        knowledge_raw.strip()
        if isinstance(knowledge_raw, str) and knowledge_raw.strip()
        else None
    )
    if knowledge and knowledge.lower() in _PLACEHOLDER_KNOWLEDGE:
        knowledge = None

    title_ids = params.get("title_ids")
    clean_ids: list[str] = []
    if title_ids is not None:
        if not isinstance(title_ids, list):
            return None, "QuestionView: title_ids must be an array"
        clean_ids = [str(x).strip() for x in title_ids if x is not None and str(x).strip()]
        if not clean_ids:
            return None, "QuestionView: title_ids must not be empty when provided"

    knowledge_ids = params.get("knowledge_ids")
    clean_knowledge: list[str] = []
    if knowledge_ids is not None:
        if not isinstance(knowledge_ids, list):
            return None, "QuestionView: knowledge_ids must be an array"
        clean_knowledge = [
            str(x).strip() for x in knowledge_ids if x is not None and str(x).strip()
        ]

    title_like = [x for x in clean_ids if x.lower().startswith("question_")]
    short_codes = [x for x in clean_ids if x not in title_like]

    if title_like:
        out: dict[str, Any] = {"title_ids": title_like[:8]}
        if knowledge:
            out["knowledge"] = knowledge
        if len(short_codes) == 1:
            out["knowledge"] = short_codes[0]
        elif len(short_codes) > 1:
            out["knowledge_ids"] = short_codes[:8]
        return out, None

    if short_codes and not title_like:
        if len(short_codes) == 1:
            return {"knowledge": short_codes[0]}, None
        return {"knowledge_ids": short_codes[:8]}, None

    if clean_knowledge:
        if len(clean_knowledge) == 1:
            return {"knowledge": clean_knowledge[0]}, None
        return {"knowledge_ids": clean_knowledge[:8]}, None

    if knowledge:
        return {"knowledge": knowledge}, None
    return None, "QuestionView: title_ids or knowledge required"


def _week_range_in_params(params: dict[str, Any]) -> dict[str, Any]:
    wr = _coerce_week_range(params.get("week_range"))
    if wr is not None:
        return {"week_range": [wr[0], wr[1]]}
    return {}


def _week_student_ids_param(params: dict[str, Any]) -> dict[str, Any]:
    raw = params.get("student_ids")
    if not isinstance(raw, list):
        return {}
    clean = clean_student_ids([str(x) for x in raw])
    if not clean:
        return {}
    return {"student_ids": clean[:8]}


def normalize_week_params(params: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    kind = params.get("kind")
    cluster = params.get("cluster")
    week_extra = _week_range_in_params(params)
    student_extra = _week_student_ids_param(params)
    if kind is not None and cluster is not None:
        return None, "WeekView: kind and cluster are mutually exclusive"
    if cluster is not None:
        try:
            cluster_int = int(cluster)
        except (TypeError, ValueError):
            return None, "WeekView: cluster must be integer 0|1|2"
        if cluster_int not in (0, 1, 2):
            return None, "WeekView: cluster must be 0, 1, or 2"
        return {"kind": cluster_int + 1, **week_extra, **student_extra}, None
    if kind is not None:
        try:
            kind_int = int(kind)
        except (TypeError, ValueError):
            return None, "WeekView: kind must be integer 1|2|3"
        if kind_int not in (1, 2, 3):
            return None, "WeekView: kind must be 1, 2, or 3"
        return {"kind": kind_int, **week_extra, **student_extra}, None
    # 无 kind/cluster：展示当前选中学生的全部簇（勿一次推 3 个 kind 按钮）
    return {**week_extra, **student_extra}, None


def normalize_link(
    link: dict[str, Any],
    *,
    contract: dict[str, Any] | None = None,
) -> tuple[dict[str, Any] | None, str | None]:
    contract = contract or load_contract()
    views = _view_enum(contract)
    view = link.get("view")
    if not isinstance(view, str) or not view.strip():
        return None, "missing view"
    view = view.strip()
    if view not in views:
        return None, f"view not in contract enum ({', '.join(sorted(views))})"

    raw_params = link.get("params")
    if not isinstance(raw_params, dict):
        return None, "params must be an object"

    params = dict(raw_params)
    spec = _view_params_spec(contract, view)

    if view == "WeekView":
        normalized, err = normalize_week_params(params)
        if err:
            return None, err
        params = normalized or {}

    elif view == "QuestionView":
        normalized, err = normalize_question_params(params)
        if err:
            return None, err
        params = normalized or {}

    elif view == "StudentView":
        ids = params.get("student_ids")
        if not isinstance(ids, list) or len(ids) < 1:
            return None, "StudentView: student_ids required (minItems 1)"
        clean_ids = [str(x).strip() for x in ids if x is not None and str(x).strip()]
        if not clean_ids:
            return None, "StudentView: student_ids required (minItems 1)"
        params = {"student_ids": clean_ids}

    elif view in ("PortraitView", "ScatterView"):
        out: dict[str, Any] = {}
        if "cluster_id" in params and params["cluster_id"] is not None:
            try:
                cid = int(params["cluster_id"])
            except (TypeError, ValueError):
                return None, f"{view}: cluster_id must be integer 0|1|2"
            if cid not in (0, 1, 2):
                return None, f"{view}: cluster_id must be 0, 1, or 2"
            out["cluster_id"] = cid
        if "student_ids" in params and params["student_ids"] is not None:
            if not isinstance(params["student_ids"], list):
                return None, f"{view}: student_ids must be an array"
            clean_ids = [str(x).strip() for x in params["student_ids"] if str(x).strip()]
            if clean_ids:
                out["student_ids"] = clean_ids
        if not out:
            params = {}
        else:
            params = out

    result: dict[str, Any] = {"view": view, "params": params}
    label = link.get("label")
    if isinstance(label, str) and label.strip():
        result["label"] = label.strip()
    return result, None


def validate_link(link: dict[str, Any], *, contract: dict[str, Any] | None = None) -> tuple[dict[str, Any] | None, str | None]:
    if not isinstance(link, dict):
        return None, "link must be an object"
    return normalize_link(link, contract=contract)


def check_archetype_minimum(
    visual_links: list[dict[str, Any]],
    archetype: str | None,
    *,
    contract: dict[str, Any] | None = None,
) -> list[str]:
    if not archetype:
        return []
    contract = contract or load_contract()
    minimum = (contract.get("archetype_minimum_links") or {}).get(archetype)
    if not minimum:
        return [f"unknown archetype: {archetype}"]
    present = {link.get("view") for link in visual_links}
    warnings: list[str] = []
    for view in minimum:
        if view not in present:
            warnings.append(f"archetype {archetype}: missing recommended view {view}")
    return warnings


def consolidate_week_view_links(
    visual_links: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], str | None]:
    """Merge redundant WeekView kind=1/2/3 links into a single entry."""
    week_links = [l for l in visual_links if l.get("view") == "WeekView"]
    other = [l for l in visual_links if l.get("view") != "WeekView"]
    if len(week_links) <= 1:
        return visual_links, None

    kinds: set[int] = set()
    merged_params: dict[str, Any] = {}
    for link in week_links:
        params = link.get("params") or {}
        kind = params.get("kind")
        if kind is not None:
            try:
                kinds.add(int(kind))
            except (TypeError, ValueError):
                pass
        if "week_range" not in merged_params:
            wr = _coerce_week_range(params.get("week_range"))
            if wr is not None:
                merged_params["week_range"] = [wr[0], wr[1]]

    if len(kinds) == 1:
        only = next(iter(kinds))
        merged_params["kind"] = only
        merged = {
            "view": "WeekView",
            "params": merged_params,
            "label": f"查看周趋势（簇 {only - 1}）",
        }
    else:
        merged = {
            "view": "WeekView",
            "params": merged_params,
            "label": "查看周趋势",
        }

    warnings_note = (
        f"已合并 {len(week_links)} 个重复的 WeekView 链接为 1 个；"
        "勿对 kind 1/2/3 各推一条。"
    )
    return other + [merged], warnings_note


def validate_links(
    links: list[Any] | None,
    *,
    archetype: str | None = None,
    contract: dict[str, Any] | None = None,
) -> dict[str, Any]:
    contract = contract or load_contract()
    visual_links: list[dict[str, Any]] = []
    rejected: list[dict[str, str]] = []
    warnings: list[str] = []

    for item in links or []:
        normalized, err = validate_link(item if isinstance(item, dict) else {}, contract=contract)
        view = item.get("view", "?") if isinstance(item, dict) else "?"
        if normalized:
            visual_links.append(normalized)
        else:
            rejected.append({"view": str(view), "reason": err or "invalid link"})

    warnings.extend(check_archetype_minimum(visual_links, archetype, contract=contract))

    for link in visual_links:
        view = link.get("view")
        params = link.get("params") or {}
        if view == "PortraitView" and not params:
            warnings.append("PortraitView: cluster_id recommended")

    consolidated, merge_note = consolidate_week_view_links(visual_links)
    if merge_note:
        warnings.append(merge_note)
    visual_links = consolidated

    return {
        "visual_links": visual_links,
        "warnings": warnings,
        "rejected": rejected,
    }


def warn_week_view_missing_student_ids(
    visual_links: list[dict[str, Any]],
    filter_context: FilterContext | None,
) -> list[str]:
    """Advise when WeekView links omit student_ids (report embed needs explicit IDs)."""
    selected = (
        list(filter_context.selected_student_ids)
        if filter_context and filter_context.selected_student_ids
        else []
    )
    warnings: list[str] = []
    for link in visual_links:
        if link.get("view") != "WeekView":
            continue
        params = link.get("params") or {}
        ids = params.get("student_ids")
        if isinstance(ids, list) and clean_student_ids([str(x) for x in ids]):
            continue
        if len(selected) == 1:
            continue
        warnings.append(
            "WeekView: 建议 params.student_ids（个体仅目标 1 人；班级 2–3 代表生）；"
            "省略时报告内嵌 WeekView 可能无法渲染。"
        )
    return warnings


def enrich_week_view_week_range(
    visual_links: list[dict[str, Any]],
    filter_context: FilterContext | None,
) -> list[dict[str, Any]]:
    """Inject session week_range into WeekView links when the model omitted it."""
    if filter_context is None or filter_context.week_range is None:
        return visual_links
    wr = [filter_context.week_range[0], filter_context.week_range[1]]
    out: list[dict[str, Any]] = []
    for link in visual_links:
        if link.get("view") != "WeekView":
            out.append(link)
            continue
        params = dict(link.get("params") or {})
        if "week_range" not in params:
            params["week_range"] = wr
            link = {**link, "params": params}
        out.append(link)
    return out


def enrich_week_view_student_ids(
    visual_links: list[dict[str, Any]],
    filter_context: FilterContext | None,
) -> tuple[list[dict[str, Any]], list[str]]:
    """
    Inject real student_IDs into WeekView links.

    Strips placeholder IDs (student1, …); uses Nav selection or class samples.
    """
    if filter_context is None:
        return visual_links, []

    notes: list[str] = []
    selected = clean_student_ids(list(filter_context.selected_student_ids or ()))
    typical = sample_typical_student_ids(
        filter_context.classes or (),
        majors=filter_context.majors,
        week_range=filter_context.week_range,
        limit=3,
    )

    out: list[dict[str, Any]] = []
    for link in visual_links:
        if link.get("view") != "WeekView":
            out.append(link)
            continue
        params = dict(link.get("params") or {})
        raw_ids = params.get("student_ids")
        had_placeholders = False
        if isinstance(raw_ids, list):
            had_placeholders = any(is_placeholder_student_id(str(x)) for x in raw_ids)
        clean = clean_student_ids(
            [str(x) for x in raw_ids] if isinstance(raw_ids, list) else []
        )

        if clean:
            params["student_ids"] = clean[:8]
        elif selected:
            pick = selected[:3] if len(selected) > 1 else selected[:1]
            params["student_ids"] = pick
            notes.append(
                f"WeekView: 已注入 Nav 选中学生 {len(pick)} 人（勿使用 student1 等占位符）"
            )
        elif typical:
            params["student_ids"] = typical
            notes.append(
                f"WeekView: 已注入班级代表学生 {typical}（来自提交记录，勿编造 student_ids）"
            )
        elif had_placeholders:
            notes.append(
                "WeekView: 已移除占位 student_ids，但未能解析真实学号；"
                "请先 query_data 或确认 Nav 班级/周次。"
            )

        out.append({**link, "params": params})
    return out, notes

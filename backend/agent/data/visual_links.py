from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

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


def normalize_week_params(params: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    kind = params.get("kind")
    cluster = params.get("cluster")
    if kind is not None and cluster is not None:
        return None, "WeekView: kind and cluster are mutually exclusive"
    if cluster is not None:
        try:
            cluster_int = int(cluster)
        except (TypeError, ValueError):
            return None, "WeekView: cluster must be integer 0|1|2"
        if cluster_int not in (0, 1, 2):
            return None, "WeekView: cluster must be 0, 1, or 2"
        return {"kind": cluster_int + 1}, None
    if kind is not None:
        try:
            kind_int = int(kind)
        except (TypeError, ValueError):
            return None, "WeekView: kind must be integer 1|2|3"
        if kind_int not in (1, 2, 3):
            return None, "WeekView: kind must be 1, 2, or 3"
        return {"kind": kind_int}, None
    # 无 kind/cluster：展示当前选中学生的全部簇（勿一次推 3 个 kind 按钮）
    return {}, None


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
        knowledge = params.get("knowledge")
        if not isinstance(knowledge, str) or not knowledge.strip():
            return None, "QuestionView: knowledge is required"
        params = {"knowledge": knowledge.strip()}

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
    for link in week_links:
        params = link.get("params") or {}
        kind = params.get("kind")
        if kind is not None:
            try:
                kinds.add(int(kind))
            except (TypeError, ValueError):
                pass

    if len(kinds) == 1:
        only = next(iter(kinds))
        merged = {
            "view": "WeekView",
            "params": {"kind": only},
            "label": f"查看周趋势（簇 {only - 1}）",
        }
    else:
        merged = {
            "view": "WeekView",
            "params": {},
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

"""Semantic dataset binding: LLM resolver with heuristic fallback."""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

from common.logger import get_logger, log_event

from .binding_context import BindingContext, candidate_for_dataset_id
from .binding_validate import DatasetBindingDecision

_log = get_logger("binding_resolver")

_SYSTEM_PROMPT = """你是数据集绑定器。根据「教师当前问题」和「本会话 query 产生的数据集列表」，
选择唯一一个 dataset_id 用于接下来的 aggregate_data。

只输出一个 JSON 对象，不要 markdown，不要解释。字段：
- scope: chain_slice | class_wide | prior_turn_dataset | explicit_dataset
- dataset_id: 必须从 catalog 里选
- confidence: high | medium | low
- rationale: 一句中文
- overrides_model_ref: true/false（若应忽略模型传入的 result_ref）

规则：
- 「这些/上述/刚查的/前N条/最低N条」且刚有 limit 查询 → chain_slice，选最近、行数最少的切片。
- 「全班/整体/规模/偏科/概况/水平」等新问全班 → class_wide，选无 limit、行数大的 submit_record。
- 新一道教师题问全班时，不要选上一题留下的 limit=10 切片。
- 「刚才那份/上一问」→ prior_turn_dataset，选对应 user_turn 的 id。
"""


def _chain_keywords(text: str) -> bool:
    t = text.lower()
    keys = (
        "这些",
        "上述",
        "刚才",
        "这份",
        "前10",
        "前 10",
        "10条",
        "10 条",
        "最低",
        "汇总这",
        "记录的分",
    )
    return any(k in t for k in keys)


def _class_wide_keywords(text: str) -> bool:
    keys = (
        "全班",
        "整体",
        "规模",
        "偏科",
        "概况",
        "大致水平",
        "整体情况",
        "知识点",
        "全班同学",
    )
    return any(k in text for k in keys)


def _prior_turn_keywords(text: str) -> bool:
    keys = ("上一问", "上一轮", "刚才那份", "之前那份", "上次")
    return any(k in text for k in keys)


def heuristic_resolve(ctx: BindingContext) -> DatasetBindingDecision | None:
    if not ctx.catalog_datasets and not ctx.candidates:
        return None

    slices = [c for c in ctx.candidates if c.is_slice]
    broads = [c for c in ctx.candidates if c.is_broad_scan]
    msg = ctx.teacher_message

    def _pick_slice() -> BindingCandidate | None:
        return slices[-1] if slices else None

    def _pick_broad() -> BindingCandidate | None:
        if broads:
            return broads[-1]
        non_slice = [c for c in ctx.candidates if not c.is_slice]
        return non_slice[-1] if non_slice else None

    pick: BindingCandidate | None = None
    scope = "explicit_dataset"

    if _prior_turn_keywords(msg):
        prior = [c for c in ctx.candidates if c.user_turn < ctx.current_user_turn]
        if not prior:
            for item in reversed(ctx.catalog_datasets):
                if item.get("user_turn", 0) < ctx.current_user_turn:
                    cid = item.get("dataset_id")
                    if cid:
                        pick = candidate_for_dataset_id(ctx, str(cid))
                        scope = "prior_turn_dataset"
                        break
        else:
            pick = prior[-1]
            scope = "prior_turn_dataset"
    elif _class_wide_keywords(msg) and not _chain_keywords(msg):
        pick = _pick_broad()
        scope = "class_wide"
    elif _chain_keywords(msg):
        pick = _pick_slice()
        scope = "chain_slice"
    elif slices and broads:
        model_ref = ctx.model_input.get("result_ref")
        if model_ref:
            norm = str(model_ref).strip().replace("\\", "/")
            for c in broads:
                if c.result_ref.strip().replace("\\", "/") == norm:
                    pick = _pick_slice()
                    scope = "chain_slice"
                    break
        if not pick:
            pick = _pick_slice()
            scope = "chain_slice"

    if not pick and len(ctx.candidates) == 1:
        pick = ctx.candidates[0]
        scope = "explicit_dataset"

    if not pick or not pick.dataset_id:
        return None

    model_ref = ctx.model_input.get("result_ref")
    overrides = False
    if model_ref and pick.result_ref:
        overrides = (
            model_ref.strip().replace("\\", "/")
            != pick.result_ref.strip().replace("\\", "/")
        )

    return DatasetBindingDecision(
        scope=scope,
        dataset_id=pick.dataset_id,
        result_ref=pick.result_ref,
        confidence="medium",
        rationale=f"启发式：scope={scope}，教师问题关键词匹配。",
        overrides_model_ref=overrides,
        resolver="heuristic",
    )


def _parse_json_content(content: str) -> dict[str, Any] | None:
    text = (content or "").strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    return None


def llm_resolve(ctx: BindingContext, llm_client: Any) -> DatasetBindingDecision | None:
    if not llm_client or not getattr(llm_client, "get_client", lambda: None)():
        return None

    catalog_lines = []
    for item in ctx.catalog_datasets[-15:]:
        catalog_lines.append(
            f"- {item.get('dataset_id')}: rows={item.get('result_rows')}, "
            f"limit={item.get('query_limit')}, resource={item.get('resource')}, "
            f"user_turn={item.get('user_turn')}, current={item.get('is_current_turn')}"
        )
    query_lines = []
    for q in ctx.query_summaries:
        query_lines.append(
            f"  #{q.order_in_turn} {q.dataset_id}: rows={q.result_rows}, "
            f"limit={q.query_limit}, ref={q.result_ref}"
        )

    user_body = (
        f"教师问题：\n{ctx.teacher_message or '(无)'}\n\n"
        f"本回合 query 顺序：\n" + ("\n".join(query_lines) or "  (无)") + "\n\n"
        f"catalog：\n" + ("\n".join(catalog_lines) or "  (无)") + "\n\n"
        f"模型 aggregate 拟传：input={json.dumps(ctx.model_input, ensure_ascii=False)}, "
        f"bind={ctx.model_bind}\n"
    )

    try:
        resp = llm_client.create_completion(
            system_prompt=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_body}],
            max_tokens=256,
        )
    except Exception as exc:
        log_event(_log, logging.WARNING, "binding_resolver_llm_failed", error=str(exc))
        return None

    if not resp or not resp.choices:
        return None
    content = getattr(resp.choices[0].message, "content", None) or ""
    raw = _parse_json_content(content if isinstance(content, str) else str(content))
    if not raw or not raw.get("dataset_id"):
        return None

    dataset_id = str(raw["dataset_id"]).strip()
    cand = candidate_for_dataset_id(ctx, dataset_id)
    if not cand:
        return None

    return DatasetBindingDecision(
        scope=str(raw.get("scope") or "explicit_dataset"),
        dataset_id=dataset_id,
        result_ref=cand.result_ref,
        confidence=str(raw.get("confidence") or "medium"),
        rationale=str(raw.get("rationale") or ""),
        overrides_model_ref=bool(raw.get("overrides_model_ref")),
        resolver="llm",
    )


def resolve_binding_intent(
    ctx: BindingContext,
    llm_client: Any | None = None,
) -> DatasetBindingDecision | None:
    force = os.environ.get("BINDING_RESOLVER_FORCE", "").strip() in ("1", "true", "yes")
    disable_llm = os.environ.get("BINDING_RESOLVER_DISABLE_LLM", "").strip() in (
        "1",
        "true",
        "yes",
    )

    decision: DatasetBindingDecision | None = None
    if not disable_llm and llm_client is not None:
        decision = llm_resolve(ctx, llm_client)
        if decision:
            log_event(
                _log,
                logging.INFO,
                "binding_resolver_llm",
                dataset_id=decision.dataset_id,
                scope=decision.scope,
            )

    if decision is None:
        decision = heuristic_resolve(ctx)
        if decision:
            log_event(
                _log,
                logging.INFO,
                "binding_resolver_heuristic",
                dataset_id=decision.dataset_id,
                scope=decision.scope,
            )

    if force and decision is None and ctx.candidates:
        c = ctx.candidates[-1]
        if c.dataset_id:
            decision = DatasetBindingDecision(
                scope="explicit_dataset",
                dataset_id=c.dataset_id,
                result_ref=c.result_ref,
                resolver="force",
            )

    return decision

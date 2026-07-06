"""Dataset binding intent recognition: LLM + heuristic fallback.

Prompt changelog:
- v2: per-call aggregate binding; ref alignment priority; numbered multi-step;
  prior_turn_dataset only for user_turn < current; richer LLM user context.
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any

from common.logger import get_logger, log_event

from .context import BindingContext, candidate_for_dataset_id
from .types import BindingCandidate, DatasetBindingDecision

_log = get_logger("binding_intent")

INTENT_PROMPT_VERSION = "v2"

_DEFAULT_SYSTEM_PROMPT = """你是 aggregate_data 的数据集绑定器。每次调用只服务「当前这一次 aggregate」：
从 catalog 选出唯一 dataset_id，并判断是否保留模型传入的 result_ref。

只输出一个 JSON 对象，不要 markdown，不要解释。字段：
- scope: chain_slice | class_wide | prior_turn_dataset | explicit_dataset
- dataset_id: 必须从 catalog 里选
- confidence: high | medium | low
- rationale: 一句中文（须说明用了哪条优先级、是否保留模型 ref）
- overrides_model_ref: true/false（true=忽略/替换模型传入的 result_ref）

决策优先级（从高到低，冲突时上位胜出）：
1. 模型本次 aggregate 拟传的 input.result_ref 若与 catalog/query 顺序中某条 ref 完全一致，
   且教师话对该步无相反口径 → overrides_model_ref=false，scope=explicit_dataset，选 ref 对应 dataset。
2. 教师话中对「这一步」的明确指代：
   - 「第 N 份 / 第 N 个 query / 步骤 N 的结果 / 对第 N 份结果 aggregate」→ 对齐「本回合 query 顺序 #N」。
   - 同一条 user 消息里的编号清单（1) query… 3) aggregate 第1份… 4) aggregate 第2份…）：
     根据「拟传 ref 对应 #几」判断当前是第几步，不要两次调用都选同一个 dataset_id。
3. 自然语言歧义指代（仅当 1、2 无法确定时作主信号）：
   - 「这些/上述/刚查的/前N条/最低N条/汇总这」→ chain_slice，选 limit 小、行数少的切片。
   - 「全班/整体/规模/偏科/概况/水平/整体情况」→ class_wide，选无 limit、行数大的 broad。
4. metrics 仅作辅助：count_distinct(student_ID) 等全班指标倾向 broad；不得单独推翻 1 且 ref 与步骤一致的情况。

scope 使用边界：
- explicit_dataset：模型 ref 正确或 dataset 与步骤一致。
- chain_slice：教师要「这些/N 条/刚查的列表」。
- class_wide：教师要全班/整体口径。
- prior_turn_dataset：仅当候选 dataset 的 user_turn 严格小于 current_user_turn。
  禁止：同 turn 内编号多步、同 turn 多个 query 结果，使用 prior_turn_dataset。

overrides_model_ref 判定：
- false：拟传 ref 与 catalog 某条一致，且教师对该步无相反口径（如步骤写「第1份」而 ref 是 #1；或「这些10条」而 ref 是 limit=10）。
- true：教师说「这些/前10/刚查的」但 ref 指向 broad/full；教师说「全班/整体」但 ref 指向 limit 切片；
  ref 缺失或不在 catalog；ref 与教师对该步的编号指代不一致（如「第2份」却给了 #1 的 ref）。

输出要求：dataset_id 必须来自 catalog。若 overrides_model_ref=false，rationale 须含「保留模型 ref」。
"""


def _env_flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes")


@dataclass(frozen=True)
class IntentConfig:
    """Configuration for binding intent recognition (LLM path)."""

    model: str | None = None
    max_tokens: int = 256
    temperature: float | None = None
    system_prompt: str = field(default=_DEFAULT_SYSTEM_PROMPT)
    disable_llm: bool = False
    force_fallback: bool = False

    @classmethod
    def from_env(cls) -> IntentConfig:
        binding_model = (os.environ.get("OPENAI_MODEL_BINDING") or "").strip() or None
        return cls(
            model=binding_model,
            disable_llm=_env_flag("BINDING_RESOLVER_DISABLE_LLM"),
            force_fallback=_env_flag("BINDING_RESOLVER_FORCE"),
        )


def _normalize_ref(ref: str) -> str:
    return ref.strip().replace("\\", "/")


def _ref_query_order(ctx: BindingContext, ref: str | None) -> int | None:
    if not ref:
        return None
    norm = _normalize_ref(str(ref))
    for q in ctx.query_summaries:
        if _normalize_ref(q.result_ref) == norm:
            return q.order_in_turn
    return None


def _has_slice_and_broad(ctx: BindingContext) -> bool:
    has_slice = any(c.is_slice for c in ctx.candidates)
    has_broad = any(c.is_broad_scan for c in ctx.candidates)
    return has_slice and has_broad


def _describe_ambiguity(ctx: BindingContext) -> list[str]:
    """Summarize ambiguity signals for the LLM (intent-only, no gate import)."""
    hints: list[str] = []
    n = len(ctx.candidates)
    if n >= 2:
        hints.append(f"MULTI_CANDIDATE(count={n})")
    if n >= 2 and _has_slice_and_broad(ctx):
        hints.append("MULTI_CANDIDATE_SLICE_BROAD")
    model_ref = ctx.model_input.get("result_ref")
    if model_ref:
        order = _ref_query_order(ctx, str(model_ref))
        if order is None:
            hints.append("MODEL_REF_NOT_IN_CURRENT_TURN_QUERIES")
        else:
            hints.append(f"MODEL_REF_MATCHES_QUERY_#{order}")
    elif not ctx.model_input.get("dataset_id"):
        hints.append("MODEL_REF_MISSING")
    if _prior_turn_keywords(ctx.teacher_message):
        hints.append("TEACHER_PRIOR_TURN_KEYWORDS")
    if _chain_keywords(ctx.teacher_message):
        hints.append("TEACHER_CHAIN_KEYWORDS")
    if _class_wide_keywords(ctx.teacher_message):
        hints.append("TEACHER_CLASS_WIDE_KEYWORDS")
    if not hints:
        hints.append("NONE")
    return hints


def build_llm_user_body(ctx: BindingContext) -> str:
    """Assemble user message for binding intent LLM (exported for tests)."""
    catalog_lines = []
    for item in ctx.catalog_datasets[-15:]:
        catalog_lines.append(
            f"- {item.get('dataset_id')}: rows={item.get('result_rows')}, "
            f"limit={item.get('query_limit')}, resource={item.get('resource')}, "
            f"user_turn={item.get('user_turn')}, current={item.get('is_current_turn')}, "
            f"ref={item.get('result_ref')}"
        )
    query_lines = []
    for q in ctx.query_summaries:
        query_lines.append(
            f"  #{q.order_in_turn} {q.dataset_id}: rows={q.result_rows}, "
            f"limit={q.query_limit}, ref={q.result_ref}"
        )

    model_ref = ctx.model_input.get("result_ref")
    ref_order = _ref_query_order(ctx, str(model_ref) if model_ref else None)
    ref_hint = (
        f"拟传 ref 对齐本回合 query #{ref_order}"
        if ref_order is not None
        else ("拟传 ref 未在本回合 query 顺序中" if model_ref else "未传 result_ref")
    )
    ambiguity = ", ".join(_describe_ambiguity(ctx))
    metrics_json = json.dumps(ctx.model_metrics, ensure_ascii=False)

    return (
        f"current_user_turn: {ctx.current_user_turn}\n"
        f"歧义信号: {ambiguity}\n"
        f"{ref_hint}\n\n"
        f"教师问题：\n{ctx.teacher_message or '(无)'}\n\n"
        f"本回合 query 顺序（#N 为第 N 次 query，含 ref）：\n"
        + ("\n".join(query_lines) or "  (无)")
        + "\n\n"
        f"catalog：\n"
        + ("\n".join(catalog_lines) or "  (无)")
        + "\n\n"
        f"模型本次 aggregate 拟传：\n"
        f"  input={json.dumps(ctx.model_input, ensure_ascii=False)}\n"
        f"  metrics={metrics_json}\n"
        f"  bind={ctx.model_bind}\n\n"
        f"请为本「这一次」aggregate 选出 dataset_id，并判断是否保留拟传 result_ref。"
    )


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


def llm_resolve(
    ctx: BindingContext,
    llm_client: Any,
    *,
    config: IntentConfig,
) -> DatasetBindingDecision | None:
    if not llm_client or not getattr(llm_client, "get_client", lambda: None)():
        return None

    user_body = build_llm_user_body(ctx)

    try:
        resp = llm_client.create_completion(
            system_prompt=config.system_prompt,
            messages=[{"role": "user", "content": user_body}],
            max_tokens=config.max_tokens,
            model=config.model,
            langfuse_name="binding_intent",
            langfuse_metadata={"purpose": "binding_intent"},
        )
    except Exception as exc:
        log_event(_log, logging.WARNING, "binding_intent_llm_failed", error=str(exc))
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
    *,
    config: IntentConfig | None = None,
) -> DatasetBindingDecision | None:
    cfg = config or IntentConfig.from_env()

    decision: DatasetBindingDecision | None = None
    if not cfg.disable_llm and llm_client is not None:
        decision = llm_resolve(ctx, llm_client, config=cfg)
        if decision:
            log_event(
                _log,
                logging.INFO,
                "binding_intent_llm",
                dataset_id=decision.dataset_id,
                scope=decision.scope,
            )

    if decision is None:
        decision = heuristic_resolve(ctx)
        if decision:
            log_event(
                _log,
                logging.INFO,
                "binding_intent_heuristic",
                dataset_id=decision.dataset_id,
                scope=decision.scope,
            )

    if cfg.force_fallback and decision is None and ctx.candidates:
        c = ctx.candidates[-1]
        if c.dataset_id:
            decision = DatasetBindingDecision(
                scope="explicit_dataset",
                dataset_id=c.dataset_id,
                result_ref=c.result_ref,
                resolver="force",
            )

    return decision

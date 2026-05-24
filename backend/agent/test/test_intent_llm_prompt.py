"""Binding intent LLM prompt and llm_resolve (mocked)."""

import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

AGENT_ROOT = Path(__file__).resolve().parents[1]
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))

import runtime_bootstrap  # noqa: F401, E402

from loop_state import AnalysisToolContext, QuerySnapshot  # noqa: E402
from tools.runtime.binding.context import build_binding_context  # noqa: E402
from tools.runtime.binding.intent import (  # noqa: E402
    INTENT_PROMPT_VERSION,
    IntentConfig,
    build_llm_user_body,
    llm_resolve,
    resolve_binding_intent,
)

FOUR_STEP_TEACHER = (
    "请对 Class1 依次完成：1) query_data：submit_record，按 score 升序 limit=10；"
    "2) query_data：submit_record 全量（不要 limit）；"
    "3) aggregate_data：对第 1 份结果算 count 和 mean(score)；"
    "4) aggregate_data：对第 2 份结果算 count_distinct(student_ID) 和 mean(score)。"
    "第 3、4 步请在 input 里显式写对应的 result_ref，不要用 bind=auto 省略。"
)


def _analysis_ctx(msg: str) -> AnalysisToolContext:
    ctx = AnalysisToolContext(session_id="intent-prompt-test", user_turn=1)
    ctx.current_user_message = msg
    return ctx


def _slice_and_broad_snaps():
    slice_snap = QuerySnapshot(
        "query-results/slice10.json",
        result_rows=10,
        query_limit=10,
        rows_scanned=22960,
        dataset_id="ds_slice",
        resource="submit_record",
    )
    broad_snap = QuerySnapshot(
        "query-results/full.json",
        result_rows=22960,
        rows_scanned=22960,
        dataset_id="ds_full",
        resource="submit_record",
    )
    return slice_snap, broad_snap


def _binding_ctx(
    *,
    teacher: str,
    model_input: dict,
    metrics: list[dict],
    batch: list[QuerySnapshot],
    analysis: AnalysisToolContext,
):
    for snap in batch:
        analysis.register_query_snapshot(snap)
    return build_binding_context(
        inp=model_input,
        metrics=metrics,
        dimensions=None,
        bind="auto",
        analysis_context=analysis,
        batch_snapshots=batch,
    )


def _mock_llm_client(response_json: dict) -> MagicMock:
    client = MagicMock()
    client.get_client.return_value = object()
    choice = MagicMock()
    choice.message.content = json.dumps(response_json, ensure_ascii=False)
    resp = MagicMock()
    resp.choices = [choice]
    client.create_completion.return_value = resp
    return client


def test_user_body_includes_per_call_context():
    analysis = _analysis_ctx(FOUR_STEP_TEACHER)
    slice_snap, broad_snap = _slice_and_broad_snaps()
    bctx = _binding_ctx(
        teacher=FOUR_STEP_TEACHER,
        model_input={"result_ref": "query-results/slice10.json"},
        metrics=[
            {"op": "count", "field": "index"},
            {"op": "mean", "field": "score"},
        ],
        batch=[slice_snap, broad_snap],
        analysis=analysis,
    )
    body = build_llm_user_body(bctx)
    assert "current_user_turn: 1" in body
    assert "MULTI_CANDIDATE_SLICE_BROAD" in body
    assert "MODEL_REF_MATCHES_QUERY_#1" in body
    assert "拟传 ref 对齐本回合 query #1" in body
    assert "metrics=" in body
    assert "#1 ds_slice" in body
    assert "#2 ds_full" in body
    assert "请为本「这一次」aggregate" in body


def test_llm_resolve_keeps_explicit_slice_ref_on_step3():
    analysis = _analysis_ctx(FOUR_STEP_TEACHER)
    slice_snap, broad_snap = _slice_and_broad_snaps()
    bctx = _binding_ctx(
        teacher=FOUR_STEP_TEACHER,
        model_input={"result_ref": "query-results/slice10.json"},
        metrics=[
            {"op": "count", "field": "index"},
            {"op": "mean", "field": "score"},
        ],
        batch=[slice_snap, broad_snap],
        analysis=analysis,
    )
    llm = _mock_llm_client(
        {
            "scope": "explicit_dataset",
            "dataset_id": "ds_slice",
            "confidence": "high",
            "rationale": "保留模型 ref，对齐 query #1",
            "overrides_model_ref": False,
        }
    )
    decision = llm_resolve(bctx, llm, config=IntentConfig())
    assert decision is not None
    assert decision.dataset_id == "ds_slice"
    assert decision.result_ref == "query-results/slice10.json"
    assert decision.overrides_model_ref is False
    assert decision.scope == "explicit_dataset"
    system_prompt = llm.create_completion.call_args.kwargs["system_prompt"]
    assert "prior_turn_dataset" in system_prompt
    assert INTENT_PROMPT_VERSION == "v2"


def test_llm_resolve_keeps_explicit_broad_ref_on_step4():
    analysis = _analysis_ctx(FOUR_STEP_TEACHER)
    slice_snap, broad_snap = _slice_and_broad_snaps()
    bctx = _binding_ctx(
        teacher=FOUR_STEP_TEACHER,
        model_input={"result_ref": "query-results/full.json"},
        metrics=[
            {"op": "count_distinct", "field": "student_ID", "as": "students"},
            {"op": "mean", "field": "score", "as": "avg_score"},
        ],
        batch=[slice_snap, broad_snap],
        analysis=analysis,
    )
    llm = _mock_llm_client(
        {
            "scope": "explicit_dataset",
            "dataset_id": "ds_full",
            "confidence": "high",
            "rationale": "保留模型 ref，对齐 query #2",
            "overrides_model_ref": False,
        }
    )
    decision = llm_resolve(bctx, llm, config=IntentConfig())
    assert decision is not None
    assert decision.dataset_id == "ds_full"
    assert decision.result_ref == "query-results/full.json"
    assert decision.overrides_model_ref is False


def test_llm_resolve_overrides_broad_ref_when_teacher_says_these():
    teacher = (
        "先找出 Class1 得分最低的前 10 条提交，再汇总这些记录的分数分布（条数、均值）。"
    )
    analysis = _analysis_ctx(teacher)
    slice_snap, broad_snap = _slice_and_broad_snaps()
    bctx = _binding_ctx(
        teacher=teacher,
        model_input={"result_ref": "query-results/full.json"},
        metrics=[
            {"op": "count", "field": "score", "as": "n"},
            {"op": "mean", "field": "score", "as": "avg"},
        ],
        batch=[slice_snap, broad_snap],
        analysis=analysis,
    )
    llm = _mock_llm_client(
        {
            "scope": "chain_slice",
            "dataset_id": "ds_slice",
            "confidence": "high",
            "rationale": "教师要汇总这些记录，改绑 limit=10 切片",
            "overrides_model_ref": True,
        }
    )
    decision = llm_resolve(bctx, llm, config=IntentConfig())
    assert decision is not None
    assert decision.dataset_id == "ds_slice"
    assert decision.overrides_model_ref is True
    assert decision.scope == "chain_slice"
    body = build_llm_user_body(bctx)
    assert "TEACHER_CHAIN_KEYWORDS" in body


def test_resolve_binding_intent_falls_back_to_heuristic_when_llm_disabled():
    os.environ["BINDING_RESOLVER_DISABLE_LLM"] = "1"
    try:
        teacher = (
            "先找出 Class1 得分最低的前 10 条提交，再汇总这些记录的分数分布（条数、均值）。"
        )
        analysis = _analysis_ctx(teacher)
        slice_snap, broad_snap = _slice_and_broad_snaps()
        bctx = _binding_ctx(
            teacher=teacher,
            model_input={"result_ref": "query-results/full.json"},
            metrics=[{"op": "count", "field": "score"}],
            batch=[slice_snap, broad_snap],
            analysis=analysis,
        )
        decision = resolve_binding_intent(bctx, llm_client=MagicMock())
        assert decision is not None
        assert decision.resolver == "heuristic"
        assert decision.dataset_id == "ds_slice"
    finally:
        os.environ.pop("BINDING_RESOLVER_DISABLE_LLM", None)

"""Preview budget + TopK aggregate + classified oscillation redirects."""

from __future__ import annotations

import json
import sys
from pathlib import Path

AGENT_ROOT = Path(__file__).resolve().parents[1]
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))

import runtime_bootstrap  # noqa: F401, E402

from data.aggregate import AggregateSpec, execute_aggregate  # noqa: E402
from data.result_hints import enrich_query_payload  # noqa: E402
from data.result_store import save_result  # noqa: E402
from hints.data_chain_guard import (  # noqa: E402
    KIND_PREVIEW_THRASH,
    build_oscillation_event,
    format_oscillation_hint,
    normalize_success_agg_signature,
    should_break_preview_requery_oscillation,
)


def _seed_ref(tmp_path, monkeypatch, n: int = 86) -> str:
    monkeypatch.setattr("data.result_store.AGENT_STATE_DIR", tmp_path, raising=False)
    monkeypatch.setattr(
        "data.result_store.QUERY_RESULTS_DIR",
        tmp_path / "task_outputs" / "query-results",
        raising=False,
    )
    rows = [{"student_ID": f"s{i:02d}", "score": float(i)} for i in range(n)]
    payload = {
        "schema": [{"name": "student_ID", "type": "string"}, {"name": "score", "type": "number"}],
        "rows": rows,
        "meta": {"resource": "submit_record"},
    }
    return save_result(payload)


def test_aggregate_keeps_preview_budget(tmp_path, monkeypatch):
    ref = _seed_ref(tmp_path, monkeypatch, n=86)
    out = execute_aggregate(
        AggregateSpec(
            input={"result_ref": ref},
            metrics=[{"op": "mean", "field": "score", "as": "avg"}, {"op": "count", "as": "n"}],
            dimensions=["student_ID"],
        ),
        preview_limit=50,
    )
    assert out["meta"].get("truncated") is True
    assert len(out["rows"]) == 50
    assert out["meta"]["full_row_count"] == 86
    assert out["meta"].get("next_actions")
    assert any(a.get("action") == "rank_topk" for a in out["meta"]["next_actions"])


def test_aggregate_order_by_limit_topk(tmp_path, monkeypatch):
    ref = _seed_ref(tmp_path, monkeypatch, n=86)
    out = execute_aggregate(
        AggregateSpec(
            input={"result_ref": ref},
            metrics=[{"op": "mean", "field": "score", "as": "avg"}],
            dimensions=["student_ID"],
            order_by=[{"field": "avg", "dir": "asc"}],
            limit=5,
        ),
        preview_limit=50,
    )
    assert out["meta"].get("truncated") is False
    assert len(out["rows"]) == 5
    assert out["meta"].get("aggregate_limit") == 5
    # lowest scores first
    avgs = [row[1] if isinstance(row, list) else row.get("avg") for row in out["rows"]]
    # tabular rows are lists aligned to schema
    schema = [c["name"] for c in out["schema"]]
    avg_idx = schema.index("avg")
    values = [float(r[avg_idx]) for r in out["rows"]]
    assert values == sorted(values)
    assert values[0] <= values[-1]


def test_truncated_warning_points_to_new_method_not_requery():
    payload = {
        "rows": [{"a": 1}] * 10,
        "meta": {"truncated": True, "result_ref": "query-results/x.json", "rows_scanned": 100},
    }
    enrich_query_payload(payload, resource="submit_record", group_by=None, limit=None)
    warnings = " ".join(payload["meta"].get("warnings") or [])
    assert "PREVIEW_ONLY" in warnings
    assert "order_by" in warnings and "limit" in warnings
    assert "省略 limit 后重新 query_data" not in warnings


def test_classified_oscillation_soft_vs_hard_copy():
    soft = build_oscillation_event(KIND_PREVIEW_THRASH, soft=True)
    hard = build_oscillation_event(KIND_PREVIEW_THRASH, soft=False)
    soft_text = format_oscillation_hint(soft)
    hard_text = format_oscillation_hint(hard)
    assert "进度提醒" in soft_text
    assert "换方法" in soft_text
    assert "order_by" in soft_text
    assert "熔断" in hard_text
    assert soft.kind == hard.kind == KIND_PREVIEW_THRASH


def test_topk_signature_not_treated_as_unordered_thrash():
    calls = [
        {
            "id": "1",
            "name": "aggregate_data",
            "arguments": {
                "dimensions": ["student_ID"],
                "metrics": [{"op": "mean", "field": "score", "as": "avg"}],
                "order_by": [{"field": "avg", "dir": "asc"}],
                "limit": 5,
            },
        }
    ]
    results = [{"tool_call_id": "1", "content": '{"meta":{"truncated":false}}'}]
    sig = normalize_success_agg_signature(calls, results)
    assert sig is not None
    parsed = json.loads(sig)
    assert parsed["ordered"] is True
    assert parsed["limited"] is True
    # repeating TopK success should not trip unordered thrash helper alone
    assert not should_break_preview_requery_oscillation([sig, sig], threshold=3)

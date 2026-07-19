"""Tests for session query_data reuse (fingerprint short-circuit)."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

AGENT_ROOT = Path(__file__).resolve().parents[1]
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))

import runtime_bootstrap  # noqa: F401, E402

from data.dataset_registry import DatasetRecord, append_dataset, list_datasets  # noqa: E402
from data.query_reuse import (  # noqa: E402
    build_query_fingerprints,
    find_reusable_dataset,
    load_reused_payload,
)
from data.result_store import save_result  # noqa: E402
from tools.handlers import data_tools  # noqa: E402
from tools.runtime.binding.rules import (  # noqa: E402
    cross_turn_reject_message,
    missing_turn_query_message,
)


def test_exact_fingerprint_stable():
    a = build_query_fingerprints(
        resource="submit_record",
        resolve_params={"class": "Class2"},
        where={
            "op": "and",
            "conditions": [
                {"field": "week_index", "op": "gte", "value": 13},
                {"field": "week_index", "op": "lte", "value": 15},
            ],
        },
        select=["student_ID", "score", "title_ID"],
        limit=None,
    )
    b = build_query_fingerprints(
        resource="submit_record",
        resolve_params={"class": "Class2"},
        where={
            "op": "and",
            "conditions": [
                {"field": "week_index", "op": "lte", "value": 15},
                {"field": "week_index", "op": "gte", "value": 13},
            ],
        },
        select=["title_ID", "score", "student_ID"],
        limit=None,
    )
    assert a[0] == b[0]
    assert a[1] == b[1]


def test_find_reusable_exact_and_compatible(tmp_path, monkeypatch):
    monkeypatch.setattr("data.dataset_registry.AGENT_STATE_DIR", tmp_path, raising=False)
    monkeypatch.setattr("data.result_store.AGENT_STATE_DIR", tmp_path, raising=False)
    monkeypatch.setattr("data.result_store.QUERY_RESULTS_DIR", tmp_path / "task_outputs" / "query-results", raising=False)

    exact, core, select_cols, lim = build_query_fingerprints(
        resource="submit_record",
        resolve_params={"class": "Class2"},
        where={"field": "week_index", "op": "eq", "value": 13},
        select=["student_ID", "score", "title_ID"],
        limit=None,
    )
    payload = {
        "resource": "submit_record",
        "columns": [{"name": "student_ID"}, {"name": "score"}, {"name": "title_ID"}],
        "rows": [["1", 1.0, "t1"]],
        "meta": {"rows_scanned": 1},
    }
    ref = save_result(payload)
    append_dataset(
        "sess-reuse",
        DatasetRecord(
            dataset_id="ds_full",
            result_ref=ref,
            user_turn=1,
            resource="submit_record",
            result_rows=1,
            query_limit=None,
            query_fingerprint=exact,
            query_core_fingerprint=core,
            select_cols=select_cols,
        ),
    )

    hit = find_reusable_dataset(
        "sess-reuse",
        exact_fp=exact,
        core_fp=core,
        select_cols=select_cols,
        limit=None,
    )
    assert hit is not None
    assert hit.dataset_id == "ds_full"

    # Subset select on same core → compatible reuse
    _e2, core2, sel2, _ = build_query_fingerprints(
        resource="submit_record",
        resolve_params={"class": "Class2"},
        where={"field": "week_index", "op": "eq", "value": 13},
        select=["student_ID", "score"],
        limit=None,
    )
    assert core2 == core
    hit2 = find_reusable_dataset(
        "sess-reuse",
        exact_fp="deadbeef",
        core_fp=core2,
        select_cols=sel2,
        limit=None,
    )
    assert hit2 is not None
    assert hit2.dataset_id == "ds_full"

    reused = load_reused_payload(hit2)
    assert reused is not None
    assert reused["meta"]["reused"] is True
    assert reused["meta"]["dataset_id"] == "ds_full"


def test_run_query_data_reuses_without_execute(tmp_path, monkeypatch):
    monkeypatch.setattr("data.dataset_registry.AGENT_STATE_DIR", tmp_path, raising=False)
    monkeypatch.setattr("data.result_store.AGENT_STATE_DIR", tmp_path, raising=False)
    monkeypatch.setattr("data.result_store.QUERY_RESULTS_DIR", tmp_path / "task_outputs" / "query-results", raising=False)

    exact, core, select_cols, _ = build_query_fingerprints(
        resource="student_info",
        resolve_params={},
        where=None,
        select=None,
        limit=None,
    )
    payload = {
        "resource": "student_info",
        "columns": [{"name": "student_ID"}],
        "rows": [["s1"]],
        "meta": {"rows_scanned": 1, "truncated": False},
    }
    ref = save_result(payload)
    append_dataset(
        "sess-q",
        DatasetRecord(
            dataset_id="ds_stu",
            result_ref=ref,
            user_turn=1,
            resource="student_info",
            result_rows=1,
            query_fingerprint=exact,
            query_core_fingerprint=core,
            select_cols=select_cols,
        ),
    )

    called = {"n": 0}

    def _boom(*_a, **_k):
        called["n"] += 1
        raise AssertionError("execute_query should not run on reuse")

    monkeypatch.setattr(data_tools, "execute_query", _boom)
    monkeypatch.setattr(
        data_tools,
        "normalize_query_resource",
        lambda resource, kwargs, where=None: (resource, kwargs, []),
    )
    monkeypatch.setattr(
        data_tools,
        "repair_submit_record_week_usage",
        lambda resource, kwargs, where=None, group_by=None, order_by=None: (
            resource,
            kwargs,
            where,
            group_by,
            order_by,
            [],
        ),
    )
    monkeypatch.setattr(data_tools, "validate_resolve_params", lambda *_a, **_k: None)
    monkeypatch.setattr(data_tools, "normalize_limit", lambda limit: (limit, None))
    monkeypatch.setattr(
        data_tools,
        "_resolve_params_with_context",
        lambda kwargs, fc, **kw: {},
    )
    monkeypatch.setattr(data_tools, "_enrich_query_payload", lambda payload, notes=None: payload)
    monkeypatch.setattr(data_tools, "enrich_query_payload", lambda payload, **kw: payload)

    # Rebuild fingerprints to match empty resolve for student_info
    exact2, core2, sel2, _ = build_query_fingerprints(
        resource="student_info",
        resolve_params={},
        where=None,
        select=None,
        limit=None,
    )
    assert exact2 == exact

    raw = data_tools.run_query_data(
        resource="student_info",
        _session_id="sess-q",
    )
    assert called["n"] == 0
    out = json.loads(raw)
    assert out["meta"]["reused"] is True
    assert out["meta"]["dataset_id"] == "ds_stu"


def test_cross_turn_messages_prefer_dataset_id():
    msg = cross_turn_reject_message(None)
    assert "dataset_id" in msg
    assert "list_datasets" in msg
    # Re-query is last resort, not co-equal option
    assert msg.index("dataset_id") < msg.index("重新 query_data")
    msg2 = missing_turn_query_message(None)
    assert "list_datasets" in msg2
    assert "dataset_id" in msg2

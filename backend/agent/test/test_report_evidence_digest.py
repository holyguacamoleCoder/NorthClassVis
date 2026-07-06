"""Report Evidence digest: ds/ref cite resolution and mislabeled aggregate refs."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

import runtime_bootstrap  # noqa: F401

_BACKEND_ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

AGENT_ROOT = Path(__file__).resolve().parents[1]
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))

from data.dataset_registry import DatasetRecord, append_dataset  # noqa: E402
from data.result_store import save_result  # noqa: E402
from agent.http.adapter import (  # noqa: E402
    _parse_tool_result_ref,
    _turn_data_snapshots,
    adapt_legacy_query_response,
)
from report.digest import (  # noqa: E402
    build_report_evidence_digest,
    resolve_ds_cite,
    validate_cites_against_session,
)
from report.evidence_cites import (  # noqa: E402
    EvidenceCite,
    validate_evidence_section,
)


def test_resolve_ds_cite_from_catalog():
    session_id = "sess_catalog_test"
    append_dataset(
        session_id,
        DatasetRecord(
            dataset_id="ds_known01",
            result_ref="query-results/known-query.json",
            user_turn=1,
            resource="submit_record",
            result_rows=100,
        ),
    )
    out = resolve_ds_cite(session_id, "ds_known01")
    assert out is not None
    assert out["verifiable"] is True
    assert out["dataset_id"] == "ds_known01"
    assert out["row_count"] == 100


def test_resolve_ds_cite_mislabeled_aggregate_ref():
    ref_id = "a1b2c3d4e5f6478990abcdef12345678"
    save_result(
        {
            "schema": [{"name": "students", "type": "integer"}],
            "rows": [[92]],
            "meta": {"resource": "submit_record", "truncated": False},
        },
        ref_id=ref_id,
    )
    out = resolve_ds_cite(None, ref_id)
    assert out is not None
    assert out["verifiable"] is True
    assert out["result_ref"] == f"query-results/{ref_id}.json"
    assert out.get("note")
    assert "[@ref:" in out["note"]


def test_resolve_ds_cite_mislabeled_aggregate_ref_path():
    ref_id = "b2c3d4e5f6478990abcdef1234567890"
    save_result(
        {
            "schema": [{"name": "students", "type": "integer"}],
            "rows": [[92]],
            "meta": {"resource": "submit_record", "truncated": False},
        },
        ref_id=ref_id,
    )
    out = resolve_ds_cite(None, f"query-results/{ref_id}")
    assert out is not None
    assert out["verifiable"] is True
    assert out["result_ref"] == f"query-results/{ref_id}.json"
    assert out.get("note")
    assert "[@ref:" in out["note"]


def test_validate_mislabeled_ds_is_warning_not_unknown():
    ref = "query-results/deadbeefdeadbeefdeadbeefdeadbeef.json"
    save_result(
        {"schema": [], "rows": [[1]], "meta": {"resource": "submit_record"}},
        ref_id="deadbeefdeadbeefdeadbeefdeadbeef",
    )
    cites = [EvidenceCite(kind="ds", target="deadbeefdeadbeefdeadbeefdeadbeef", summary=None, raw="")]
    errors, warnings = validate_cites_against_session(
        cites,
        known_dataset_ids=set(),
        known_result_refs=set(),
        validation_level="deliver",
    )
    assert not errors
    assert any("实为 result_ref" in w for w in warnings)


def test_validate_evidence_section_warns_ds_uuid_shape():
    body = "[@ds:70b45c43f80c471fb1869b5b8ef0dd60]"
    result = validate_evidence_section(body)
    assert any("实为 result_ref" in w for w in result.warnings)


def test_parse_tool_result_from_compacted_summary():
    content = (
        "[Earlier tool result compacted. Re-run the tool if you need full detail.]\n"
        "[Summary] resource=submit_record, result_ref=query-results/"
        "70b45c43f80c471fb1869b5b8ef0dd60.json, rows_scanned=16566"
    )
    ref, meta = _parse_tool_result_ref(content)
    assert ref == "query-results/70b45c43f80c471fb1869b5b8ef0dd60.json"
    assert meta == {}


def test_turn_data_snapshots_includes_aggregate():
    ref = "query-results/715f0eaf0b2943909bb249fed8e7044d.json"
    messages = [
        {
            "role": "assistant",
            "tool_calls": [
                {
                    "id": "c1",
                    "function": {"name": "aggregate_data", "arguments": "{}"},
                }
            ],
        },
        {
            "role": "tool",
            "tool_call_id": "c1",
            "content": json.dumps(
                {
                    "schema": [{"name": "avg_score", "type": "number"}],
                    "rows": [[1.1]],
                    "meta": {"resource": "submit_record", "result_ref": ref},
                }
            ),
        },
    ]
    snaps = _turn_data_snapshots(messages)
    assert len(snaps) == 1
    assert snaps[0].result_ref == ref
    assert snaps[0].result_rows == 1


def test_adapt_legacy_report_evidence_resolves_mislabeled_ds(tmp_path, monkeypatch):
    from common.paths import DATA_DIR

    ref_id = "70b45c43f80c471fb1869b5b8ef0dd60"
    save_result(
        {
            "schema": [{"name": "students", "type": "integer"}, {"name": "avg_score", "type": "number"}],
            "rows": [[92.0, 1.103]],
            "meta": {"resource": "submit_record", "truncated": False, "rows_scanned": 16566},
        },
        ref_id=ref_id,
    )

    rel = "reports/class/class2/overview.md"
    dest = DATA_DIR / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        "# R\n\n## evidence\n\n"
        f"数据 [@ds:{ref_id}]\n",
        encoding="utf-8",
    )

    messages = [
        {"role": "user", "content": "写报告"},
        {
            "role": "assistant",
            "tool_calls": [
                {
                    "id": "a1",
                    "function": {"name": "aggregate_data", "arguments": "{}"},
                },
                {
                    "id": "w1",
                    "function": {"name": "write_file", "arguments": json.dumps({"path": rel})},
                },
            ],
        },
        {
            "role": "tool",
            "tool_call_id": "a1",
            "content": json.dumps(
                {
                    "rows": [[92.0, 1.103]],
                    "meta": {"result_ref": f"query-results/{ref_id}.json", "resource": "submit_record"},
                }
            ),
        },
        {"role": "tool", "tool_call_id": "w1", "content": f"[Write OK: path={rel}, bytes=10]"},
        {"role": "assistant", "content": "完成"},
    ]
    out = adapt_legacy_query_response(messages, session_id="sess_evidence_fix")
    evidence = out["report_evidence"]
    assert len(evidence) == 1
    assert evidence[0]["verifiable"] is True
    assert evidence[0].get("row_count") == 1
    assert evidence[0].get("note")
    assert "dataset_id not in session catalog" not in str(evidence[0].get("error", ""))


def test_build_report_evidence_digest_catalog_ds():
    session_id = "sess_build_digest"
    append_dataset(
        session_id,
        DatasetRecord(
            dataset_id="ds_aa4a0e47bc05",
            result_ref="query-results/660fdc28c8a24e478e1d24ed8384ca03.json",
            user_turn=1,
            resource="submit_record",
            result_rows=16566,
        ),
    )
    items = build_report_evidence_digest(
        "[@ds:ds_aa4a0e47bc05]",
        session_id=session_id,
    )
    assert len(items) == 1
    assert items[0]["verifiable"] is True
    assert items[0]["dataset_id"] == "ds_aa4a0e47bc05"

"""Working-set ref resolution (memory layer)."""

import sys
from pathlib import Path

AGENT_ROOT = Path(__file__).resolve().parents[1]
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))

from loop_state import AnalysisToolContext, QuerySnapshot  # noqa: E402
from tools.runtime.data_chain import working_result_ref  # noqa: E402


def test_working_prefers_last_in_batch_not_smaller_limit():
    ctx = AnalysisToolContext()
    ctx.register_query_snapshot(
        QuerySnapshot("query-results/old-limit.json", result_rows=10, query_limit=10)
    )
    batch = [
        QuerySnapshot("query-results/full.json", result_rows=22960),
    ]
    assert working_result_ref(batch, ctx) == "query-results/full.json"


def test_working_uses_turn_pointer_when_batch_empty():
    ctx = AnalysisToolContext()
    ctx.working_active_ref = "query-results/turn.json"
    assert working_result_ref([], ctx) == "query-results/turn.json"


def test_working_empty_after_begin_user_turn():
    ctx = AnalysisToolContext()
    ctx.working_active_ref = "query-results/stale.json"
    ctx.begin_user_turn()
    assert working_result_ref([], ctx) is None

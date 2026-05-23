import importlib.util
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parent.parent
AGENT_ROOT = BACKEND_ROOT / "agent"
for path in (BACKEND_ROOT, AGENT_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("numpy") is None,
    reason="numpy 未安装，跳过依赖数据分析栈的资源注册表测试",
)

pytest.importorskip("pandas")

from data import (  # noqa: E402  # backend/agent/data
    FilterContext,
    QueryLimits,
    dataframe_to_tabular,
    resolve,
    validate_tabular_result,
)
from data.exceptions import InvalidParameterError, UnknownResourceError  # noqa: E402
from data.registry import list_agent_resource_ids, list_resource_ids  # noqa: E402


@pytest.fixture
def data_dir():
    return BACKEND_ROOT.parent / "data"


def test_metrics_resources_resolve(data_dir):
    for resource_id in ("submit_record_joined", "week_aggregation"):
        resolved = resolve(resource_id, data_dir=data_dir)
        assert resolved.resource_id == resource_id
        assert resolved.kind == "derived"


def test_resolve_student_and_title_schema_columns(data_dir):
    student = resolve("student_info", data_dir=data_dir)
    title = resolve("title_info", data_dir=data_dir)

    student_df = student.load()
    title_df = title.load()

    assert list(student_df.columns) == student.schema_columns
    assert list(title_df.columns) == title.schema_columns
    assert "student_ID" in student_df.columns
    assert "title_ID" in title_df.columns


def test_submit_record_class1(data_dir):
    resolved = resolve("submit_record", classes=["Class1"], data_dir=data_dir)
    df = resolved.load()
    assert len(df) > 0
    assert "knowledge" in df.columns
    assert "major" in df.columns
    assert "student_ID" in df.columns
    assert "title_ID" in df.columns


def test_submit_record_joined_class1(data_dir):
    resolved = resolve("submit_record_joined", classes=["Class1"], data_dir=data_dir)
    df = resolved.load()
    assert len(df) > 0
    assert "knowledge" in df.columns
    assert "student_ID" in df.columns
    assert "title_ID" in df.columns


def test_week_aggregation_series_columns(data_dir):
    resolved = resolve("week_aggregation", classes=["Class1"], data_dir=data_dir)
    df = resolved.load()
    assert set(df.columns) >= {"student_ID", "week_index", "peak_value", "direction"}
    if not df.empty:
        assert df["week_index"].dtype in ("int64", "int32", "int")
        assert df["direction"].isin(["up", "down", "flat"]).all()


def test_truncated_when_over_max_rows(data_dir):
    resolved = resolve("submit_record_joined", classes=["Class1"], data_dir=data_dir)
    df = resolved.load()
    tabular = dataframe_to_tabular(
        df,
        "submit_record_joined",
        limits=QueryLimits(max_rows=10),
    )
    assert tabular["meta"]["truncated"] is True
    assert len(tabular["rows"]) <= 10
    assert tabular["meta"]["rows_scanned"] > 10


def test_tabular_validates_against_schema(data_dir):
    resolved = resolve("student_info", data_dir=data_dir)
    df = resolved.load().head(5)
    payload = dataframe_to_tabular(df, "student_info")
    validate_tabular_result(payload)
    assert payload["meta"]["resource"] == "student_info"


def test_unknown_resource_raises():
    with pytest.raises(UnknownResourceError):
        resolve("not_a_resource")


def test_invalid_class_raises(data_dir):
    with pytest.raises(InvalidParameterError):
        resolve("submit_record_joined", classes=["Class999"], data_dir=data_dir).load()
    with pytest.raises(InvalidParameterError):
        resolve("submit_record_joined", classes=["NotAClass"], data_dir=data_dir).load()


def test_filter_context_to_params():
    ctx = FilterContext(
        classes=("Class1",),
        majors=("J23517",),
        week_range=(0, 4),
        selected_student_ids=("abc",),
    )
    params = ctx.to_resolve_params()
    assert params["classes"] == ["Class1"]
    assert params["majors"] == ["J23517"]
    assert params["week_range"] == [0, 4]
    assert params["student_ids"] == ["abc"]


def test_all_registry_ids_listed():
    ids = list_resource_ids()
    assert "student_info" in ids
    assert "submit_record" in ids
    assert "submit_record_joined" in ids
    assert "week_aggregation" in ids


def test_agent_resource_ids_hide_internal_alias():
    agent_ids = list_agent_resource_ids()
    assert "submit_record" in agent_ids
    assert "submit_record_joined" not in agent_ids
    assert "week_aggregation" in agent_ids

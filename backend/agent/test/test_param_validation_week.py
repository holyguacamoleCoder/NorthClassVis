"""Week dimension auto-repair on submit_record queries."""

import runtime_bootstrap  # noqa: F401

from data.param_validation import repair_submit_record_week_usage


def test_repair_group_by_week_index_switches_resource():
    resource, kwargs, where, group_by, order_by, notes = repair_submit_record_week_usage(
        "submit_record",
        {"class": "Class1", "classes": ["Class1"]},
        where={
            "op": "and",
            "conditions": [
                {"field": "student_ID", "op": "eq", "value": "8b6d1125760bd3939b6e"},
            ],
        },
        group_by=["week_index"],
        order_by=[{"dir": "asc", "field": "week_index"}],
    )
    assert resource == "week_aggregation"
    assert kwargs["classes"] == ["Class1"]
    assert group_by == ["week_index"]
    assert order_by == [{"dir": "asc", "field": "week_index"}]
    assert where is not None
    assert any("week_aggregation" in n for n in notes)


def test_repair_extracts_week_range_from_where():
    resource, kwargs, where, _, _, notes = repair_submit_record_week_usage(
        "submit_record",
        {"classes": ["Class1"]},
        where={
            "op": "and",
            "conditions": [
                {"field": "week_index", "op": "gte", "value": 13},
                {"field": "week_index", "op": "lte", "value": 15},
                {"field": "student_ID", "op": "eq", "value": "s1"},
            ],
        },
        group_by=["week_index"],
    )
    assert resource == "week_aggregation"
    assert kwargs.get("week_range") == [13, 15]
    assert where == {"field": "student_ID", "op": "eq", "value": "s1"}
    assert any("week_range" in n for n in notes)


def test_no_repair_without_week_dimension():
    resource, _, where, _, _, notes = repair_submit_record_week_usage(
        "submit_record",
        {"classes": ["Class1"]},
        where={"field": "student_ID", "op": "eq", "value": "s1"},
        group_by=["major"],
    )
    assert resource == "submit_record"
    assert notes == []
    assert where is not None

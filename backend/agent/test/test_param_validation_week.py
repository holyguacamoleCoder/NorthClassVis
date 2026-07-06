"""Week dimension auto-repair on submit_record queries."""

import runtime_bootstrap  # noqa: F401

from data.param_validation import repair_submit_record_week_usage


def test_no_auto_switch_when_submit_record_has_week_index():
    resource, kwargs, where, group_by, order_by, notes = repair_submit_record_week_usage(
        "submit_record",
        {"class": "Class1", "classes": ["Class1"]},
        where={
            "op": "and",
            "conditions": [
                {"field": "week_index", "op": "gte", "value": 13},
                {"field": "week_index", "op": "lte", "value": 15},
            ],
        },
        group_by=["week_index"],
        order_by=[{"dir": "asc", "field": "week_index"}],
    )
    assert resource == "submit_record"
    assert kwargs["classes"] == ["Class1"]
    assert group_by == ["week_index"]
    assert notes == []
    assert where is not None


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

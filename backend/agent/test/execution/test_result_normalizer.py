"""execution/result_normalizer.py：extract_tool_results。"""

from agent.execution import extract_tool_results


def test_extract_tool_results_maps_full_fields():
    raw = [
        {
            "tool": "query_class",
            "input": {"mode": "trend"},
            "status": "ok",
            "summary": "ok",
            "evidence": [{"tool": "query_class", "summary": "s"}],
            "visual_hints": [{"view": "WeekView", "params": {"kind": 1}}],
            "raw": {"x": 1},
            "duration_ms": 12,
            "coverage": {"covered": True},
            "quality": {"score": 0.9},
            "error": "",
        }
    ]
    out = extract_tool_results(raw)
    assert len(out) == 1
    one = out[0]
    assert one.tool == "query_class"
    assert one.params == {"mode": "trend"}
    assert one.status == "ok"
    assert one.summary == "ok"
    assert one.evidence[0]["tool"] == "query_class"
    assert one.visual_hints[0]["view"] == "WeekView"
    assert one.raw == {"x": 1}
    assert one.duration_ms == 12
    assert one.coverage == {"covered": True}
    assert one.quality == {"score": 0.9}
    assert one.error == ""


def test_extract_tool_results_fills_defaults():
    out = extract_tool_results([{}])
    assert len(out) == 1
    one = out[0]
    assert one.tool == ""
    assert one.params == {}
    assert one.status == "ok"
    assert one.summary == ""
    assert one.evidence == []
    assert one.visual_hints == []
    assert one.duration_ms == 0
    assert one.coverage == {}
    assert one.quality == {}
    assert one.error == ""


def test_extract_tool_results_handles_empty_input():
    assert extract_tool_results([]) == []
    assert extract_tool_results(None) == []

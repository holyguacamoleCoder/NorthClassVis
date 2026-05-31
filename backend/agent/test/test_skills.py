import sys
from pathlib import Path

import runtime_bootstrap  # noqa: F401, E402

BACKEND_ROOT = Path(__file__).resolve().parents[2]
AGENT_ROOT = BACKEND_ROOT / "agent"
REPO_ROOT = AGENT_ROOT.parents[1]

from permission import CapabilityMode, filter_tools
from permission.modes import MODE_TOOL_ALLOWLIST
from skills import SkillRegistry, reset_registry
from skills.registry import _parse_frontmatter
from tools.definitions.registry import TOOL_DISPATCHER
from tools.definitions.schemas import TOOLS
from tools.handlers.load_skill import _FALLBACK_LOADED, run_load_skill


def test_parse_frontmatter():
    text = "---\nname: demo\ndescription: A demo skill\n---\n\nBody here.\n"
    meta, body = _parse_frontmatter(text)
    assert meta["name"] == "demo"
    assert meta["description"] == "A demo skill"
    assert body.strip() == "Body here."


def test_registry_discovers_skills(tmp_path):
    skill_dir = tmp_path / "my-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\nname: my-skill\ndescription: Test skill\n---\n\nDo the thing.\n",
        encoding="utf-8",
    )
    registry = SkillRegistry(skills_dir=tmp_path)
    assert "my-skill" in registry.documents
    assert "my-skill" in registry.describe_available()
    loaded = registry.load_full_text("my-skill")
    assert '<skill name="my-skill">' in loaded
    assert "Do the thing." in loaded


def test_registry_discovers_reference_docs(tmp_path):
    ref = tmp_path / "reference"
    ref.mkdir()
    (ref / "demo-ref.md").write_text(
        "---\nname: demo-ref\ndescription: A reference doc skill\n---\n\nRef body.\n",
        encoding="utf-8",
    )
    registry = SkillRegistry(skills_dir=tmp_path)
    assert "demo-ref" in registry.documents
    assert "Ref body." in registry.load_full_text("demo-ref")


def test_registry_unknown_skill(tmp_path):
    registry = SkillRegistry(skills_dir=tmp_path)
    result = registry.load_full_text("missing")
    assert "Error: Unknown skill" in result
    assert registry.describe_available() == "(no skills available)"


def test_load_skill_tool_with_registry(tmp_path):
    skill_dir = tmp_path / "alpha"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\nname: alpha\ndescription: Alpha\n---\n\nAlpha body.\n",
        encoding="utf-8",
    )
    reset_registry(SkillRegistry(skills_dir=tmp_path))
    try:
        _FALLBACK_LOADED.clear()
        loaded: set[str] = set()
        first = run_load_skill("alpha", _loaded_skills=loaded)
        assert "[Skill loaded: alpha]" in first
        assert "已加载技能" in first
        second = run_load_skill("alpha", _loaded_skills=loaded)
        assert "Skill active: alpha" in second or "already" in second.lower()
        assert "Error" in run_load_skill("")
        assert "Unknown skill" in run_load_skill("nope")
        assert "load_skill" in TOOL_DISPATCHER
    finally:
        reset_registry(None)


def test_load_skill_in_mode_allowlists():
    for mode in CapabilityMode:
        allowed = MODE_TOOL_ALLOWLIST[mode]
        if mode == CapabilityMode.CONSULT:
            assert "load_skill" in allowed
        else:
            assert "load_skill" in allowed


def test_filter_tools_includes_load_skill_in_analyze():
    filtered = filter_tools(TOOLS, CapabilityMode.ANALYZE)
    names = {s["function"]["name"] for s in filtered}
    assert "load_skill" in names
    assert "write_file" not in names


def test_builtin_skills_present():
    repo_skills = REPO_ROOT / "skills"
    if not repo_skills.is_dir():
        return
    registry = SkillRegistry(skills_dir=repo_skills)
    for name in (
        "analysis-student",
        "analysis-class",
        "analysis-major",
        "data-exploration",
        "report-delivery",
    ):
        assert name in registry.documents, f"missing skill: {name}"

    assert "tiered-report" not in registry.documents

    catalog = registry.describe_available()
    for name in (
        "analysis-student",
        "analysis-class",
        "analysis-major",
        "data-exploration",
        "report-delivery",
    ):
        assert name in catalog

    for name in ("analysis-student", "analysis-class", "analysis-major", "data-exploration"):
        desc = registry.documents[name].manifest.description
        assert len(desc) >= 80, f"{name} description too short: {len(desc)}"

    student_body = registry.documents["analysis-student"].body
    for section_id in (
        "scope",
        "week_trend",
        "student_structure",
        "question_anchors",
        "peer_context",
        "actions",
    ):
        assert section_id in student_body
    assert "reports/student" in student_body
    assert "report-delivery" in student_body
    assert student_body.count("```report-chart") == 0
    assert "每章：结论" not in student_body
    assert "read_file" in student_body and "reports/" in student_body

    class_body = registry.documents["analysis-class"].body
    assert "distribution" in class_body
    assert "typical_students" in class_body
    assert "reports/class" in class_body
    assert "academic_analysis_<ClassN>_reference" not in class_body
    assert "作版式参考" not in class_body
    assert "dashboard_views" not in class_body
    assert class_body.count("```report-chart") == 0

    major_body = registry.documents["analysis-major"].body
    assert "reports/major" in major_body
    assert major_body.count("```report-chart") == 0

    delivery_doc = registry.documents["report-delivery"]
    assert delivery_doc.manifest.path.name == "report-delivery.md"
    assert (repo_skills / "reference" / "report-delivery.md").is_file()
    assert "报告 Markdown 结构" in delivery_doc.body
    assert "禁止" in delivery_doc.body and "read_file" in delivery_doc.body

    assert not (REPO_ROOT / "data" / "meta" / "report_delivery.md").is_file()


if __name__ == "__main__":
    import tempfile

    test_parse_frontmatter()
    with tempfile.TemporaryDirectory() as tmp:
        test_registry_discovers_skills(Path(tmp))
    with tempfile.TemporaryDirectory() as tmp:
        test_registry_discovers_reference_docs(Path(tmp))
    with tempfile.TemporaryDirectory() as tmp:
        test_registry_unknown_skill(Path(tmp))
    with tempfile.TemporaryDirectory() as tmp:
        test_load_skill_tool_with_registry(Path(tmp))
    test_load_skill_in_mode_allowlists()
    test_filter_tools_includes_load_skill_in_analyze()
    test_builtin_skills_present()
    print("test_skills: ok")

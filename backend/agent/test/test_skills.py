import sys
import os
from pathlib import Path

import runtime_bootstrap  # noqa: F401, E402

BACKEND_ROOT = Path(__file__).resolve().parents[2]
AGENT_ROOT = BACKEND_ROOT / "agent"
REPO_ROOT = AGENT_ROOT.parents[1]

from common.system_prompt import SystemPromptBuilder, SystemPromptContext
from permission import CapabilityMode, filter_tools
from permission.modes import MODE_TOOL_ALLOWLIST
from skills import SkillRegistry, reset_registry
from skills.registry import SKILL_ALIASES, _parse_frontmatter, catalog_skill_names
from slash_commands import list_skills_payload
from tools.definitions.registry import TOOL_DISPATCHER
from tools.definitions.schemas import TOOLS
from tools.handlers.load_skill import _FALLBACK_LOADED, run_load_skill
from tools.handlers.load_reference import run_load_reference


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


def test_registry_does_not_merge_reference_md(tmp_path):
    skill_dir = tmp_path / "demo-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\nname: demo-skill\ndescription: Demo skill\n---\n\nSkill body.\n",
        encoding="utf-8",
    )
    (skill_dir / "reference.md").write_text("# Ref\n\nRef detail.\n", encoding="utf-8")
    registry = SkillRegistry(skills_dir=tmp_path)
    body = registry.documents["demo-skill"].body
    assert "Skill body." in body
    assert "Ref detail." not in body


def test_registry_report_delivery_alias(tmp_path):
    skill_dir = tmp_path / "report-writing"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\nname: report-writing\ndescription: Reports\n---\n\nRW body.\n",
        encoding="utf-8",
    )
    registry = SkillRegistry(skills_dir=tmp_path)
    assert "report-writing" in registry.documents
    assert "report-delivery" in registry.documents
    assert registry.load_full_text("report-delivery").startswith('<skill name="report-writing">')


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
        assert '✅ Skill "alpha"' in first
        assert "Alpha body." in first
        assert "<skill" in first
        second = run_load_skill("alpha", _loaded_skills=loaded)
        assert "Skill active: alpha" in second
        assert "Error" in run_load_skill("")
        assert "Unknown skill" in run_load_skill("nope")
        assert "load_skill" in TOOL_DISPATCHER
    finally:
        reset_registry(None)


def test_load_skill_in_mode_allowlists():
    for mode in CapabilityMode:
        allowed = MODE_TOOL_ALLOWLIST[mode]
        assert "load_skill" in allowed
        assert "load_reference" in allowed


def test_filter_tools_includes_load_skill_in_analyze():
    filtered = filter_tools(TOOLS, CapabilityMode.ANALYZE)
    names = {s["function"]["name"] for s in filtered}
    assert "load_skill" in names
    assert "load_reference" in names
    assert "write_file" not in names


def test_load_reference_tool_marks_loaded(tmp_path):
    ref_dir = tmp_path / "report-writing" / "references"
    ref_dir.mkdir(parents=True)
    (ref_dir / "student.md").write_text("# Student\n\nRules.\n", encoding="utf-8")

    loaded: set[str] = set()
    old_env = os.environ.get("AGENT_SKILLS_DIR")
    try:
        os.environ["AGENT_SKILLS_DIR"] = str(tmp_path)
        first = run_load_reference("student", _loaded_references=loaded)
        assert '✅ Reference "' in first
        assert "Rules." in first
        assert any("student.md" in item for item in loaded)
        second = run_load_reference("student", _loaded_references=loaded)
        assert "[Reference active:" in second
    finally:
        if old_env is None:
            os.environ.pop("AGENT_SKILLS_DIR", None)
        else:
            os.environ["AGENT_SKILLS_DIR"] = old_env


def test_produce_system_prompt_lists_report_writing_in_catalog():
    """Produce mode mentions report-writing via skills catalog / base prompt, not loaded-names section."""
    registry = SkillRegistry(skills_dir=REPO_ROOT / "skills")
    if not registry.documents.get("report-writing"):
        return
    prompt = SystemPromptBuilder().build(
        SystemPromptContext(
            permission_mode="produce",
            skills=registry,
            loaded_skills=[],
        )
    )
    assert "report-writing" in prompt
    from common.prompts import SECTION_LOADED_NAMES

    assert SECTION_LOADED_NAMES not in prompt


def test_list_skills_payload_excludes_aliases():
    repo_skills = REPO_ROOT / "skills"
    if not repo_skills.is_dir():
        return
    registry = SkillRegistry(skills_dir=repo_skills)
    names = [r["name"] for r in list_skills_payload(registry)]
    assert "report-delivery" not in names
    assert "report-writing" in names
    assert names == catalog_skill_names(registry)


def test_builtin_skills_present():
    repo_skills = REPO_ROOT / "skills"
    if not repo_skills.is_dir():
        return
    registry = SkillRegistry(skills_dir=repo_skills)
    for name in ("data-exploration", "report-writing"):
        assert name in registry.documents, f"missing skill: {name}"

    assert "tiered-report" not in registry.documents
    assert "report-delivery" in registry.documents  # alias
    assert not (repo_skills / "reference" / "report-delivery.md").is_file()

    catalog = registry.describe_available()
    for name in ("data-exploration", "report-writing"):
        assert name in catalog
    assert "report-delivery" not in catalog

    rw = registry.documents["report-writing"]
    assert (repo_skills / "report-writing" / "SKILL.md").is_file()
    assert not (repo_skills / "report-writing" / "reference.md").is_file()
    assert "report-chart" in rw.body
    assert "reports/notes" in rw.body

    assert SKILL_ALIASES.get("report-delivery") == "report-writing"
    assert not (REPO_ROOT / "data" / "meta" / "report_delivery.md").is_file()


if __name__ == "__main__":
    import tempfile

    test_parse_frontmatter()
    with tempfile.TemporaryDirectory() as tmp:
        test_registry_discovers_skills(Path(tmp))
    with tempfile.TemporaryDirectory() as tmp:
        test_registry_does_not_merge_reference_md(Path(tmp))
    with tempfile.TemporaryDirectory() as tmp:
        test_registry_report_delivery_alias(Path(tmp))
    with tempfile.TemporaryDirectory() as tmp:
        test_registry_unknown_skill(Path(tmp))
    with tempfile.TemporaryDirectory() as tmp:
        test_load_skill_tool_with_registry(Path(tmp))
    test_load_skill_in_mode_allowlists()
    test_filter_tools_includes_load_skill_in_analyze()
    test_produce_system_prompt_lists_report_writing_in_catalog()
    test_builtin_skills_present()
    print("test_skills: ok")

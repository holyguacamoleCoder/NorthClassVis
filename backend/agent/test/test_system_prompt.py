import sys
import tempfile
from pathlib import Path

AGENT_ROOT = Path(__file__).resolve().parents[1]
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))

from common.memory import MemoryManager
from common.prompts import (
    MEMORY_GUIDANCE,
    PERMISSION_MODE_TEMPLATE,
    SECTION_SESSION,
    build_base_agent_prompt,
    format_permission_mode,
)
from common.system_prompt import SystemPromptBuilder, SystemPromptContext
from permission import CapabilityMode, filter_tools
from permission.modes import MODE_TOOL_ALLOWLIST
from skills import SkillRegistry
from tools.definitions.schemas import TOOLS


def test_memory_save_and_prompt_section(tmp_path=None):
    base = tmp_path or Path(tempfile.mkdtemp())
    mgr = MemoryManager(memory_dir=base / ".memory")
    mgr.save_memory("prefer_tabs", "Use tabs", "user", "Always indent with tabs.")
    mgr.load_all()
    section = mgr.load_memory_prompt()
    assert "prefer_tabs" in section
    assert "Always indent with tabs" in section


def test_system_prompt_builder_includes_sections(tmp_path=None):
    base = tmp_path or Path(tempfile.mkdtemp())
    mem = MemoryManager(memory_dir=base / ".memory")
    skill_dir = base / "skills"
    skill_dir.mkdir()
    (skill_dir / "demo-skill").mkdir()
    (skill_dir / "demo-skill" / "SKILL.md").write_text(
        "---\nname: demo-skill\ndescription: Demo\n---\n\nBody.\n",
        encoding="utf-8",
    )
    registry = SkillRegistry(skills_dir=skill_dir)
    prompt = SystemPromptBuilder(memory=mem).build(
        SystemPromptContext(
            permission_mode="analyze",
            session_context=["catalog: data/meta/data_catalog.md"],
            skills=registry,
        )
    )
    assert build_base_agent_prompt("analyze").strip() in prompt
    assert "NorthClassVision" in prompt
    assert format_permission_mode("analyze") in prompt
    assert SECTION_SESSION in prompt
    assert "catalog: data/meta/data_catalog.md" in prompt
    assert "demo-skill" in prompt
    assert MEMORY_GUIDANCE.strip() in prompt


def test_prompt_templates_are_complete():
    assert "{mode}" in PERMISSION_MODE_TEMPLATE
    assert "{mode_hint}" in PERMISSION_MODE_TEMPLATE
    consult = format_permission_mode("consult")
    assert "consult" in consult
    assert "schema" in consult
    assert "produce" in format_permission_mode("produce")
    assert "report-chart" in build_base_agent_prompt("produce")
    assert "不可用" in build_base_agent_prompt("consult")
    # consult base still mentions build_visual_links / report-chart in the load_skill table
    assert "build_visual_links" in build_base_agent_prompt("consult")


def test_base_prompt_mode_slices_differ():
    consult = build_base_agent_prompt("consult")
    produce = build_base_agent_prompt("produce")
    assert "consult" in consult.lower()
    assert "report-chart" in produce
    assert consult != produce


def test_save_memory_in_analyze_mode():
    """memory / save_memory are registered and allowed in analyze mode."""
    names = {t["function"]["name"] for t in TOOLS}
    assert "memory" in names
    assert "save_memory" in names
    visible = filter_tools(TOOLS, CapabilityMode.ANALYZE)
    visible_names = {t["function"]["name"] for t in visible}
    assert "memory" in visible_names
    assert "save_memory" in visible_names
    assert "memory" in MODE_TOOL_ALLOWLIST[CapabilityMode.ANALYZE]
    assert "save_memory" in MODE_TOOL_ALLOWLIST[CapabilityMode.ANALYZE]


if __name__ == "__main__":
    test_memory_save_and_prompt_section()
    test_system_prompt_builder_includes_sections()
    test_save_memory_in_analyze_mode()
    test_prompt_templates_are_complete()
    print("test_system_prompt: ok")

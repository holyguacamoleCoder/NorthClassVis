import sys
import tempfile
from pathlib import Path

AGENT_ROOT = Path(__file__).resolve().parents[1]
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))

from slash_commands import execute_slash_command, parse_slash_command
from session import SessionManager
from skills import SkillRegistry, reset_registry


def test_parse_skill_command():
    cmd = parse_slash_command("/skill")
    assert cmd is not None
    assert cmd.kind == "skill"
    assert parse_slash_command("/skills list") is not None
    assert parse_slash_command("/skill analysis-class").args == ["analysis-class"]
    assert parse_slash_command("hello") is None


def test_execute_skill_list_and_load():
    with tempfile.TemporaryDirectory() as tmp:
        skill_dir = Path(tmp) / "skills"
        skill_dir.mkdir()
        (skill_dir / "alpha").mkdir()
        (skill_dir / "alpha" / "SKILL.md").write_text(
            "---\nname: alpha\ndescription: Alpha skill\n---\n\nAlpha body.\n",
            encoding="utf-8",
        )
        registry = SkillRegistry(skills_dir=skill_dir)
        reset_registry(registry)
        try:
            sm = SessionManager(skills=registry)
            sm.create_session(permission_mode="analyze")
            listed = execute_slash_command(
                sm,
                registry,
                parse_slash_command("/skill"),
                user_line="/skill",
            )
            assert "alpha" in listed["answer"]
            assert listed["loaded_skills"] == []

            loaded = execute_slash_command(
                sm,
                registry,
                parse_slash_command("/skill alpha"),
                user_line="/skill alpha",
            )
            assert "alpha" in loaded["loaded_skills"]
            assert loaded["trace"]["steps"][0]["tool"] == "load_skill"
        finally:
            reset_registry(None)


if __name__ == "__main__":
    test_parse_skill_command()
    test_execute_skill_list_and_load()
    print("test_slash_commands: ok")

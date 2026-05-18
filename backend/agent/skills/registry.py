import os
import re
from pathlib import Path

from .manifest import SkillDocument, SkillManifest

BASE_DIR = Path(__file__).resolve().parents[3]  # NorthClassVision
DEFAULT_SKILLS_DIR = BASE_DIR / "skills"


def _parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    match = re.match(r"^---\n(.*?)\n---\n(.*)", text, re.DOTALL)
    if not match:
        return {}, text
    meta: dict[str, str] = {}
    for line in match.group(1).strip().splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        meta[key.strip()] = value.strip()
    return meta, match.group(2)


class SkillRegistry:
    """Discover SKILL.md files and load bodies on demand."""

    def __init__(self, skills_dir: Path | None = None):
        env_dir = os.environ.get("AGENT_SKILLS_DIR", "").strip()
        if skills_dir is not None:
            self.skills_dir = skills_dir
        elif env_dir:
            self.skills_dir = Path(env_dir)
        else:
            self.skills_dir = DEFAULT_SKILLS_DIR
        self.documents: dict[str, SkillDocument] = {}
        self._load_all()

    def _load_all(self) -> None:
        if not self.skills_dir.exists():
            return
        for path in sorted(self.skills_dir.rglob("SKILL.md")):
            meta, body = _parse_frontmatter(path.read_text(encoding="utf-8"))
            name = meta.get("name", path.parent.name)
            description = meta.get("description", "No description")
            manifest = SkillManifest(name=name, description=description, path=path)
            self.documents[name] = SkillDocument(manifest=manifest, body=body.strip())

    def describe_available(self) -> str:
        if not self.documents:
            return "(no skills available)"
        lines = []
        for name in sorted(self.documents):
            manifest = self.documents[name].manifest
            lines.append(f"- {manifest.name}: {manifest.description}")
        return "\n".join(lines)

    def load_full_text(self, name: str) -> str:
        document = self.documents.get(name)
        if not document:
            known = ", ".join(sorted(self.documents)) or "(none)"
            return f"Error: Unknown skill '{name}'. Available skills: {known}"
        return (
            f'<skill name="{document.manifest.name}">\n'
            f"{document.body}\n"
            "</skill>"
        )


_default_registry: SkillRegistry | None = None


def get_registry() -> SkillRegistry:
    global _default_registry
    if _default_registry is None:
        _default_registry = SkillRegistry()
    return _default_registry


def reset_registry(registry: SkillRegistry | None = None) -> None:
    global _default_registry
    _default_registry = registry

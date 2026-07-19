"""Persistent cross-session memories (backend/.agent/memory/*.md)."""

from __future__ import annotations

import logging
import os
import re
import time
from pathlib import Path
from typing import Any

from common.logger import get_logger, log_event
from common.memory_policy import session_scoped_memory_error
from common.paths import LEGACY_MEMORY_DIRS, MEMORY_DIR, PROJECT_ROOT, bootstrap_agent_paths
from common.prompts import (
    SECTION_MEMORY_TITLE,
    format_memory_entry_header,
    format_memory_type_header,
)

_log = get_logger("memory")

MEMORY_TYPES = ("user", "feedback", "project", "reference")
MEMORY_TARGETS = ("user", "memory")
MEMORY_ACTIONS = ("add", "replace", "remove")
MAX_INDEX_LINES = 200
MAX_MEMORY_CONTENT_CHARS = 4000
# System-prompt injection budget (index mode keeps descriptions + short previews).
MAX_PROMPT_MEMORY_CHARS = 2400
ENTRY_BODY_PREVIEW_CHARS = 120

_SECRET_PATTERNS = (
    re.compile(r"api[_-]?key\s*=", re.I),
    re.compile(r"secret\s*=", re.I),
    re.compile(r"password\s*=", re.I),
    re.compile(r"Bearer\s+[A-Za-z0-9._-]{20,}", re.I),
)

# Rolling journals (reference tool: target user | memory).
ROLLING_TARGETS: dict[str, dict[str, str]] = {
    "user": {
        "stem": "user_profile",
        "type": "user",
        "description": "Teacher preferences, role, and habits",
    },
    "memory": {
        "stem": "agent_notes",
        "type": "project",
        "description": "Workflow, environment, and project conventions",
    },
}

ROLLING_MEMORY_STEMS = frozenset(meta["stem"] for meta in ROLLING_TARGETS.values())


def memory_kind(key: str) -> str:
    """rolling = user_profile/agent_notes journal; named = standalone .md files."""
    return "rolling" if key in ROLLING_MEMORY_STEMS else "named"

_DATA_DUMP_HINTS = (
    "resource_registry",
    "submit_record,",
    "column layout",
    "字段列表",
)


def safe_memory_name(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]", "_", (name or "").lower())


def parse_enabled_flag(raw: str | None) -> bool:
    if raw is None or str(raw).strip() == "":
        return True
    return str(raw).strip().lower() in ("true", "yes", "1", "on")


class MemoryManager:
    """Load, build, and save persistent memories across sessions."""

    def __init__(self, memory_dir: Path | None = None):
        if memory_dir is None:
            bootstrap_agent_paths()
        self.memory_dir = memory_dir or MEMORY_DIR
        self.memories: dict[str, dict] = {}

    def load_all(self) -> int:
        """Load all memory files. Returns count loaded."""
        self.memories = {}
        if not self.memory_dir.exists():
            for legacy in LEGACY_MEMORY_DIRS:
                if legacy.is_dir() and any(legacy.glob("*.md")):
                    self.memory_dir = legacy
                    break
            else:
                return 0
        for md_file in sorted(self.memory_dir.glob("*.md")):
            if md_file.name == "MEMORY.md":
                continue
            parsed = self._parse_frontmatter(md_file.read_text(encoding="utf-8"))
            if parsed:
                display_name = parsed.get("name", md_file.stem)
                key = safe_memory_name(display_name) or md_file.stem
                self.memories[key] = {
                    "name": display_name,
                    "description": parsed.get("description", ""),
                    "type": parsed.get("type", "project"),
                    "content": parsed.get("content", ""),
                    "enabled": parse_enabled_flag(parsed.get("enabled")),
                    "file": md_file.name,
                    "updated_at": md_file.stat().st_mtime,
                }
        count = len(self.memories)
        if count:
            log_event(_log, logging.INFO, "memory_loaded", count=count, dir=str(self.memory_dir))
        return count

    def list_entries(self) -> list[dict[str, Any]]:
        """Public list for HTTP API (sorted by type, then name)."""
        rows: list[dict[str, Any]] = []
        for key, mem in sorted(self.memories.items(), key=lambda kv: (kv[1]["type"], kv[0])):
            content = mem.get("content") or ""
            preview = content.strip().replace("\n", " ")
            if len(preview) > 160:
                preview = preview[:159] + "…"
            rows.append(
                {
                    "key": key,
                    "name": mem.get("name", key),
                    "kind": memory_kind(key),
                    "type": mem["type"],
                    "description": mem.get("description", ""),
                    "enabled": bool(mem.get("enabled", True)),
                    "file": mem.get("file", ""),
                    "preview": preview,
                    "updated_at": mem.get("updated_at"),
                }
            )
        return rows

    def get_entry(self, name_or_key: str) -> dict[str, Any] | None:
        key = safe_memory_name(name_or_key) or name_or_key
        mem = self.memories.get(key)
        if mem is None:
            for k, v in self.memories.items():
                if v.get("name") == name_or_key or k == name_or_key:
                    mem = v
                    key = k
                    break
        if mem is None:
            return None
        return {
            "key": key,
            "name": mem.get("name", key),
            "kind": memory_kind(key),
            "type": mem["type"],
            "description": mem.get("description", ""),
            "content": mem.get("content", ""),
            "enabled": bool(mem.get("enabled", True)),
            "file": mem.get("file", ""),
            "updated_at": mem.get("updated_at"),
        }

    def _enabled_memories(self) -> dict[str, dict]:
        return {k: v for k, v in self.memories.items() if v.get("enabled", True)}

    def delete_entry(self, name_or_key: str) -> str:
        key = safe_memory_name(name_or_key) or name_or_key
        mem = self.memories.get(key)
        if mem is None:
            for k, v in self.memories.items():
                if v.get("name") == name_or_key:
                    mem = v
                    key = k
                    break
        if mem is None:
            return f"Error: memory not found: {name_or_key}"
        file_name = mem.get("file")
        if file_name:
            path = self.memory_dir / file_name
            if path.is_file():
                path.unlink()
        del self.memories[key]
        self._rebuild_index()
        log_event(_log, logging.INFO, "memory_deleted", name=mem.get("name", key), key=key)
        return f"[Memory removed: name={mem.get('name', key)}, action=deleted]"

    def load_memory_prompt(self, *, mode: str = "index") -> str:
        """Build a memory section for injection into the system prompt."""
        if not self._enabled_memories():
            return ""
        if (mode or "index").strip().lower() == "full":
            return self._load_memory_prompt_full()
        return self._load_memory_prompt_index()

    def _content_preview(self, content: str) -> str:
        text = (content or "").strip().replace("\n", " ")
        if len(text) <= ENTRY_BODY_PREVIEW_CHARS:
            return text
        return text[: ENTRY_BODY_PREVIEW_CHARS - 1] + "…"

    def _load_memory_prompt_full(self) -> str:
        sections = [SECTION_MEMORY_TITLE, ""]
        active = self._enabled_memories()
        for mem_type in MEMORY_TYPES:
            typed = {k: v for k, v in active.items() if v["type"] == mem_type}
            if not typed:
                continue
            sections.append(format_memory_type_header(mem_type))
            for _key, mem in sorted(typed.items(), key=lambda kv: kv[1].get("name", kv[0])):
                sections.append(
                    format_memory_entry_header(mem["name"], mem["description"])
                )
                if mem["content"].strip():
                    sections.append(mem["content"].strip())
                sections.append("")
        return "\n".join(sections)

    def _load_memory_prompt_index(self) -> str:
        sections = [SECTION_MEMORY_TITLE, ""]
        used = len(SECTION_MEMORY_TITLE) + 2
        truncated = False
        active = self._enabled_memories()
        for mem_type in MEMORY_TYPES:
            typed = {k: v for k, v in active.items() if v["type"] == mem_type}
            if not typed:
                continue
            type_header = format_memory_type_header(mem_type)
            if used + len(type_header) + 2 > MAX_PROMPT_MEMORY_CHARS:
                truncated = True
                break
            sections.append(type_header)
            used += len(type_header) + 1
            for _key, mem in sorted(typed.items(), key=lambda kv: kv[1].get("name", kv[0])):
                header = format_memory_entry_header(mem["name"], mem["description"])
                preview = self._content_preview(mem.get("content", ""))
                block_parts = [header]
                if preview:
                    block_parts.append(preview)
                block = "\n".join(block_parts) + "\n"
                if used + len(block) + 1 > MAX_PROMPT_MEMORY_CHARS:
                    truncated = True
                    break
                sections.append(block.rstrip())
                sections.append("")
                used += len(block) + 1
            if truncated:
                break
        if truncated:
            sections.append(
                "（摘要模式：部分记忆未完全注入；教师可用 /memories 或侧栏「持久记忆」查看全文。）"
            )
        return "\n".join(sections)

    def update_entry(
        self,
        name_or_key: str,
        *,
        content: str | None = None,
        description: str | None = None,
        mem_type: str | None = None,
        enabled: bool | None = None,
    ) -> str:
        entry = self.get_entry(name_or_key)
        if entry is None:
            return f"Error: memory not found: {name_or_key}"
        new_content = content if content is not None else entry["content"]
        new_desc = description if description is not None else entry["description"]
        new_type = mem_type if mem_type is not None else entry["type"]
        new_enabled = enabled if enabled is not None else entry.get("enabled", True)
        enabled_only = (
            enabled is not None
            and content is None
            and description is None
            and mem_type is None
        )
        return self.save_memory(
            entry["name"],
            new_desc,
            new_type,
            new_content,
            enabled=new_enabled,
            validate=not enabled_only,
        )

    def validate_content(self, content: str) -> str | None:
        """Return error message if content must be rejected."""
        text = (content or "").strip()
        if not text:
            return "Error: content is required and cannot be empty"
        if len(text) > MAX_MEMORY_CONTENT_CHARS:
            return (
                f"Error: content too long (max {MAX_MEMORY_CONTENT_CHARS} chars) | "
                "Keep one fact per save; use reports for large analysis output."
            )
        for pattern in _SECRET_PATTERNS:
            if pattern.search(text):
                return "Error: content looks like a secret or credential; do not save secrets."
        lower = text.lower()
        if any(hint in lower for hint in _DATA_DUMP_HINTS) and len(text) > 400:
            return (
                "Error: content looks like a data/schema dump | "
                "Use inspect_schema/query_data and report files instead."
            )
        scoped = session_scoped_memory_error(text)
        if scoped:
            return scoped
        return None

    def apply_memory(
        self,
        action: str,
        target: str,
        content: str = "",
        old_text: str = "",
    ) -> str:
        """Add/replace/remove lines in a rolling memory journal (target user | memory)."""
        action = (action or "").strip().lower()
        target = (target or "").strip().lower()
        if action not in MEMORY_ACTIONS:
            return (
                f"Error: action must be one of {MEMORY_ACTIONS} | "
                'Example: {"action":"add","target":"user","content":"…"}'
            )
        if target not in MEMORY_TARGETS:
            return (
                f"Error: target must be one of {MEMORY_TARGETS} | "
                "user=teacher preferences; memory=workflow/project notes"
            )
        meta = ROLLING_TARGETS[target]
        key = meta["stem"]
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        file_path = self.memory_dir / f"{key}.md"

        if action in ("add", "replace"):
            err = self.validate_content(content)
            if err:
                return err
        if action in ("replace", "remove"):
            needle = (old_text or "").strip()
            if not needle:
                return (
                    "Error: old_text is required for replace/remove | "
                    "Use a short unique substring from the entry to change."
                )

        if file_path.is_file():
            parsed = self._parse_frontmatter(file_path.read_text(encoding="utf-8")) or {}
            body = parsed.get("content", "")
        else:
            parsed = {}
            body = ""

        if action == "add":
            line = content.strip()
            if body.strip():
                body = f"{body.rstrip()}\n- {line}\n"
            else:
                body = f"- {line}\n"
        elif action == "replace":
            if needle not in body:
                return (
                    f"Error: old_text not found in {target} memory | "
                    f"Snippet: {needle[:80]!r}"
                )
            body = body.replace(needle, content.strip(), 1)
        else:  # remove
            if needle not in body:
                return (
                    f"Error: old_text not found in {target} memory | "
                    f"Snippet: {needle[:80]!r}"
                )
            lines = body.splitlines()
            kept = [ln for ln in lines if needle not in ln]
            if len(kept) == len(lines):
                body = body.replace(needle, "", 1)
            else:
                body = "\n".join(kept)
                if body.strip() and not body.endswith("\n"):
                    body += "\n"

        err = self.validate_content(body) if body.strip() else None
        if err and action != "remove":
            return err

        frontmatter = (
            f"---\n"
            f"name: {meta['stem']}\n"
            f"description: {meta['description']}\n"
            f"type: {meta['type']}\n"
            f"enabled: true\n"
            f"---\n"
            f"{body}"
        )
        file_path.write_text(frontmatter, encoding="utf-8")
        self.memories[key] = {
            "name": meta["stem"],
            "description": meta["description"],
            "type": meta["type"],
            "content": body.strip(),
            "enabled": True,
            "file": file_path.name,
            "updated_at": time.time(),
        }
        self._rebuild_index()
        rel = self._relative_path(file_path)
        log_event(
            _log,
            logging.INFO,
            "memory_updated",
            target=target,
            action=action,
            path=str(rel),
        )
        return (
            f"[Memory updated: target={target}, type={meta['type']}, "
            f"path={rel}, action={action}]"
        )

    def save_memory(
        self,
        name: str,
        description: str,
        mem_type: str,
        content: str,
        *,
        enabled: bool = True,
        validate: bool = True,
    ) -> str:
        if mem_type not in MEMORY_TYPES:
            return (
                f"Error: type must be one of {MEMORY_TYPES} | Example: "
                '{"name":"prefer_tabs","description":"Report uses tabs",'
                '"type":"user","content":"…"}'
            )
        if validate:
            err = self.validate_content(content)
            if err:
                return err
        safe_name = safe_memory_name(name)
        if not safe_name:
            return (
                "Error: invalid memory name (use [a-z0-9_-] only) | Example: report_style_class1"
            )
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        enabled_str = "true" if enabled else "false"
        frontmatter = (
            f"---\n"
            f"name: {name}\n"
            f"description: {description}\n"
            f"type: {mem_type}\n"
            f"enabled: {enabled_str}\n"
            f"---\n"
            f"{content.strip()}\n"
        )
        file_name = f"{safe_name}.md"
        file_path = self.memory_dir / file_name
        overwritten = file_path.exists()
        file_path.write_text(frontmatter, encoding="utf-8")
        self.memories[safe_name] = {
            "name": name,
            "description": description,
            "type": mem_type,
            "content": content.strip(),
            "enabled": enabled,
            "file": file_name,
            "updated_at": time.time(),
        }
        self._rebuild_index()
        rel = self._relative_path(file_path)
        log_event(
            _log,
            logging.INFO,
            "memory_saved",
            name=name,
            type=mem_type,
            enabled=enabled,
            path=str(rel),
        )
        action = "overwritten" if overwritten else "created"
        return (
            f"[Memory saved: name={name}, type={mem_type}, path={rel}, action={action}]"
        )

    def _relative_path(self, file_path: Path) -> str:
        try:
            return str(file_path.resolve().relative_to(PROJECT_ROOT.resolve()))
        except ValueError:
            return str(file_path)

    def _rebuild_index(self) -> None:
        lines = ["# Memory Index", ""]
        for key, mem in sorted(
            self.memories.items(),
            key=lambda kv: (kv[1]["type"], kv[1].get("name", kv[0])),
        ):
            flag = "on" if mem.get("enabled", True) else "off"
            lines.append(
                f"- {mem.get('name', key)}: {mem['description']} [{mem['type']}, {flag}]"
            )
            if len(lines) >= MAX_INDEX_LINES:
                lines.append(f"... (truncated at {MAX_INDEX_LINES} lines)")
                break
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        (self.memory_dir / "MEMORY.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _parse_frontmatter(self, text: str) -> dict | None:
        match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)", text, re.DOTALL)
        if not match:
            return None
        header, body = match.group(1), match.group(2)
        result: dict[str, str] = {"content": body.strip()}
        for line in header.splitlines():
            if ":" in line:
                key, _, value = line.partition(":")
                result[key.strip()] = value.strip()
        return result


from common.dream import DreamConsolidator, get_dream_consolidator


_default_memory: MemoryManager | None = None


def get_memory_manager() -> MemoryManager:
    global _default_memory
    if _default_memory is None:
        _default_memory = MemoryManager()
        _default_memory.load_all()
    return _default_memory

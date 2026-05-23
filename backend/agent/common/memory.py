"""Persistent cross-session memories (.memory/*.md)."""

from __future__ import annotations

import logging
import os
import re
import time
from pathlib import Path

from common.logger import get_logger, log_event
from common.paths import LEGACY_MEMORY_DIRS, MEMORY_DIR, PROJECT_ROOT, bootstrap_agent_paths
from common.prompts import (
    SECTION_MEMORY_TITLE,
    format_memory_entry_header,
    format_memory_type_header,
)

_log = get_logger("memory")

MEMORY_TYPES = ("user", "feedback", "project", "reference")
MAX_INDEX_LINES = 200


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
                name = parsed.get("name", md_file.stem)
                self.memories[name] = {
                    "description": parsed.get("description", ""),
                    "type": parsed.get("type", "project"),
                    "content": parsed.get("content", ""),
                    "file": md_file.name,
                }
        count = len(self.memories)
        if count:
            log_event(_log, logging.INFO, "memory_loaded", count=count, dir=str(self.memory_dir))
        return count

    def load_memory_prompt(self) -> str:
        """Build a memory section for injection into the system prompt."""
        if not self.memories:
            return ""
        sections = [SECTION_MEMORY_TITLE, ""]
        for mem_type in MEMORY_TYPES:
            typed = {k: v for k, v in self.memories.items() if v["type"] == mem_type}
            if not typed:
                continue
            sections.append(format_memory_type_header(mem_type))
            for name, mem in typed.items():
                sections.append(format_memory_entry_header(name, mem["description"]))
                if mem["content"].strip():
                    sections.append(mem["content"].strip())
                sections.append("")
        return "\n".join(sections)

    def save_memory(self, name: str, description: str, mem_type: str, content: str) -> str:
        if mem_type not in MEMORY_TYPES:
            return (
                f"Error: type must be one of {MEMORY_TYPES} | Example: "
                '{"name":"prefer_tabs","description":"Report uses tabs",'
                '"type":"user","content":"…"}'
            )
        safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", name.lower())
        if not safe_name:
            return (
                "Error: invalid memory name (use [a-z0-9_-] only) | Example: report_style_class1"
            )
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        frontmatter = (
            f"---\n"
            f"name: {name}\n"
            f"description: {description}\n"
            f"type: {mem_type}\n"
            f"---\n"
            f"{content}\n"
        )
        file_name = f"{safe_name}.md"
        file_path = self.memory_dir / file_name
        overwritten = file_path.exists()
        file_path.write_text(frontmatter, encoding="utf-8")
        self.memories[name] = {
            "description": description,
            "type": mem_type,
            "content": content,
            "file": file_name,
        }
        self._rebuild_index()
        try:
            rel = file_path.resolve().relative_to(PROJECT_ROOT.resolve())
        except ValueError:
            rel = file_path
        log_event(_log, logging.INFO, "memory_saved", name=name, type=mem_type, path=str(rel))
        action = "overwritten" if overwritten else "created"
        return f"[Memory saved: name={name}, type={mem_type}, path={rel}, {action}]"

    def _rebuild_index(self) -> None:
        lines = ["# Memory Index", ""]
        for name, mem in self.memories.items():
            lines.append(f"- {name}: {mem['description']} [{mem['type']}]")
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


class DreamConsolidator:
    """Optional memory consolidation between sessions."""

    COOLDOWN_SECONDS = 86400
    SCAN_THROTTLE_SECONDS = 600
    MIN_SESSION_COUNT = 5
    LOCK_STALE_SECONDS = 3600
    PHASES = [
        "Orient: scan MEMORY.md index for structure and categories",
        "Gather: read individual memory files for full content",
        "Consolidate: merge related memories, remove stale entries",
        "Prune: enforce 200-line limit on MEMORY.md index",
    ]

    def __init__(self, memory_dir: Path | None = None):
        self.memory_dir = memory_dir or MEMORY_DIR
        self.lock_file = self.memory_dir / ".dream_lock"
        self.enabled = True
        self.mode = "default"
        self.last_consolidation_time = 0.0
        self.last_scan_time = 0.0
        self.session_count = 0

    def should_consolidate(self) -> tuple[bool, str]:
        now = time.time()
        if not self.enabled:
            return False, "Gate 1: consolidation is disabled"
        if not self.memory_dir.exists():
            return False, "Gate 2: memory directory does not exist"
        memory_files = [f for f in self.memory_dir.glob("*.md") if f.name != "MEMORY.md"]
        if not memory_files:
            return False, "Gate 2: no memory files found"
        if self.mode == "plan":
            return False, "Gate 3: plan mode does not allow consolidation"
        if now - self.last_consolidation_time < self.COOLDOWN_SECONDS:
            remaining = int(self.COOLDOWN_SECONDS - (now - self.last_consolidation_time))
            return False, f"Gate 4: cooldown active, {remaining}s remaining"
        if now - self.last_scan_time < self.SCAN_THROTTLE_SECONDS:
            remaining = int(self.SCAN_THROTTLE_SECONDS - (now - self.last_scan_time))
            return False, f"Gate 5: scan throttle active, {remaining}s remaining"
        if self.session_count < self.MIN_SESSION_COUNT:
            return False, f"Gate 6: only {self.session_count} sessions, need {self.MIN_SESSION_COUNT}"
        if not self._acquire_lock():
            return False, "Gate 7: lock held by another process"
        return True, "All 7 gates passed"

    def consolidate(self) -> list[str]:
        can_run, reason = self.should_consolidate()
        if not can_run:
            log_event(_log, logging.INFO, "dream_skipped", reason=reason)
            return []
        log_event(_log, logging.INFO, "dream_start")
        self.last_scan_time = time.time()
        completed = list(self.PHASES)
        self.last_consolidation_time = time.time()
        self._release_lock()
        log_event(_log, logging.INFO, "dream_complete", phases=len(completed))
        return completed

    def _acquire_lock(self) -> bool:
        if self.lock_file.exists():
            try:
                pid_str, timestamp_str = self.lock_file.read_text(encoding="utf-8").strip().split(":", 1)
                pid = int(pid_str)
                lock_time = float(timestamp_str)
                if (time.time() - lock_time) > self.LOCK_STALE_SECONDS:
                    self.lock_file.unlink()
                else:
                    try:
                        os.kill(pid, 0)
                        return False
                    except OSError:
                        self.lock_file.unlink()
            except (ValueError, OSError):
                self.lock_file.unlink(missing_ok=True)
        try:
            self.memory_dir.mkdir(parents=True, exist_ok=True)
            self.lock_file.write_text(f"{os.getpid()}:{time.time()}", encoding="utf-8")
            return True
        except OSError:
            return False

    def _release_lock(self) -> None:
        try:
            if self.lock_file.exists():
                pid_str = self.lock_file.read_text(encoding="utf-8").strip().split(":")[0]
                if int(pid_str) == os.getpid():
                    self.lock_file.unlink()
        except (ValueError, OSError):
            pass


_default_memory: MemoryManager | None = None


def get_memory_manager() -> MemoryManager:
    global _default_memory
    if _default_memory is None:
        _default_memory = MemoryManager()
        _default_memory.load_all()
    return _default_memory

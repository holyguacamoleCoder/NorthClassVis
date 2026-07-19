"""Background memory housekeeping between sessions (no LLM / no RAG)."""

from __future__ import annotations

import json
import logging
import os
import re
import time
from pathlib import Path

from common.logger import get_logger, log_event
from common.memory_policy import session_scoped_memory_error
from common.paths import MEMORY_DIR, bootstrap_agent_paths

_log = get_logger("memory.dream")


class DreamConsolidator:
    COOLDOWN_SECONDS = 86400
    SCAN_THROTTLE_SECONDS = 600
    MIN_SESSION_COUNT = 5
    LOCK_STALE_SECONDS = 3600
    STATE_FILE = ".dream_state.json"
    PHASES = [
        "Orient: scan MEMORY.md index for structure and categories",
        "Gather: read individual memory files for full content",
        "Consolidate: merge related memories, remove stale entries",
        "Prune: enforce 200-line limit on MEMORY.md index",
    ]

    def __init__(self, memory_dir: Path | None = None):
        if memory_dir is None:
            bootstrap_agent_paths()
        self.memory_dir = memory_dir or MEMORY_DIR
        self.lock_file = self.memory_dir / ".dream_lock"
        self.enabled = True
        self.mode = "default"
        self.last_consolidation_time = 0.0
        self.last_scan_time = 0.0
        self.session_count = 0
        self._load_state()

    def _state_path(self) -> Path:
        return self.memory_dir / self.STATE_FILE

    def _load_state(self) -> None:
        path = self._state_path()
        if not path.is_file():
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return
        if not isinstance(data, dict):
            return
        self.last_consolidation_time = float(data.get("last_consolidation_time") or 0)
        self.last_scan_time = float(data.get("last_scan_time") or 0)
        self.session_count = int(data.get("session_count") or 0)
        if "enabled" in data:
            self.enabled = bool(data.get("enabled"))

    def _save_state(self) -> None:
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "last_consolidation_time": self.last_consolidation_time,
            "last_scan_time": self.last_scan_time,
            "session_count": self.session_count,
            "enabled": self.enabled,
        }
        self._state_path().write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def note_session(self) -> None:
        """Call when a new chat session is created (feeds Gate 6)."""
        self.session_count += 1
        self._save_state()

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

    def consolidate(self, *, force: bool = False) -> list[str]:
        if force:
            if not self._acquire_lock():
                log_event(_log, logging.INFO, "dream_skipped", reason="lock held")
                return []
        else:
            can_run, reason = self.should_consolidate()
            if not can_run:
                log_event(_log, logging.INFO, "dream_skipped", reason=reason)
                return []
        log_event(_log, logging.INFO, "dream_start")
        self.last_scan_time = time.time()
        completed: list[str] = []
        try:
            from common.memory import MemoryManager, memory_kind

            mgr = MemoryManager(self.memory_dir)
            mgr.load_all()
            completed.append(self.PHASES[0])
            completed.append(self.PHASES[1])
            removed = self._consolidate_entries(mgr, memory_kind)
            completed.append(self.PHASES[2])
            mgr._rebuild_index()
            completed.append(self.PHASES[3])
            self.last_consolidation_time = time.time()
            self._save_state()
            log_event(
                _log,
                logging.INFO,
                "dream_complete",
                phases=len(completed),
                removed=removed,
            )
        finally:
            self._release_lock()
        return completed

    def _consolidate_entries(self, mgr, memory_kind) -> int:
        removed = 0
        for key, mem in list(mgr.memories.items()):
            if memory_kind(key) == "rolling":
                self._dedupe_journal_lines(mgr, key, mem)
                continue
            content = (mem.get("content") or "").strip()
            if not content:
                path = self.memory_dir / str(mem.get("file") or f"{key}.md")
                path.unlink(missing_ok=True)
                mgr.memories.pop(key, None)
                removed += 1
                continue
            if session_scoped_memory_error(content):
                mem["enabled"] = False
                self._rewrite_entry(mgr, key, mem)

        seen: dict[tuple[str, str], str] = {}
        for key, mem in list(mgr.memories.items()):
            if memory_kind(key) == "rolling":
                continue
            norm = re.sub(r"\s+", " ", (mem.get("content") or "").strip().lower())
            sig = (str(mem.get("type") or "project"), norm)
            if not norm:
                continue
            if sig not in seen:
                seen[sig] = key
                continue
            path = self.memory_dir / str(mem.get("file") or f"{key}.md")
            path.unlink(missing_ok=True)
            mgr.memories.pop(key, None)
            removed += 1
        return removed

    def _dedupe_journal_lines(self, mgr, key: str, mem: dict) -> None:
        content = mem.get("content") or ""
        lines = content.splitlines()
        if len(lines) < 2:
            return
        out: list[str] = []
        prev_norm = None
        for line in lines:
            norm = re.sub(r"\s+", " ", line.strip().lower())
            if norm and norm == prev_norm:
                continue
            out.append(line)
            prev_norm = norm or prev_norm
        new_content = "\n".join(out).strip()
        if new_content == content.strip():
            return
        mem["content"] = new_content
        self._rewrite_entry(mgr, key, mem)

    def _rewrite_entry(self, mgr, key: str, mem: dict) -> None:
        file_name = str(mem.get("file") or f"{key}.md")
        path = self.memory_dir / file_name
        enabled_str = "true" if mem.get("enabled", True) else "false"
        name = mem.get("name", key)
        desc = mem.get("description", "")
        mtype = mem.get("type", "project")
        body = (mem.get("content") or "").strip()
        text = (
            "---\n"
            f"name: {name}\n"
            f"description: {desc}\n"
            f"type: {mtype}\n"
            f"enabled: {enabled_str}\n"
            "---\n"
            f"{body}\n"
        )
        path.write_text(text, encoding="utf-8")
        mgr.memories[key] = mem

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


_default_dream: DreamConsolidator | None = None


def get_dream_consolidator() -> DreamConsolidator:
    global _default_dream
    if _default_dream is None:
        _default_dream = DreamConsolidator()
    return _default_dream

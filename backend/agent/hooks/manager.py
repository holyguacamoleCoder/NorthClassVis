"""Hook system: extension points around tool execution without rewriting the loop."""

from __future__ import annotations

import json
import logging
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from common.logger import get_logger, log_event

_log = get_logger("hooks")

BASE_DIR = Path(__file__).resolve().parents[3]  # NorthClassVision

HOOK_EVENTS = ("PreToolUse", "PostToolUse", "SessionStart")
HOOK_TIMEOUT = 30

# Optional trust gate (off by default). Set AGENT_HOOKS_REQUIRE_TRUST=1 to enable.
TRUST_MARKER = BASE_DIR / ".claude" / ".claude_trusted"
DEFAULT_CONFIG_PATH = BASE_DIR / ".hooks.json"


@dataclass
class HookResult:
    blocked: bool = False
    messages: list[str] = field(default_factory=list)
    block_reason: str = ""
    permission_override: str | None = None


class HookManager:
    """
    Load and run hooks from .hooks.json.

    Exit codes: 0 continue, 1 block, 2 inject message (stderr).
    stdout JSON may include updatedInput, additionalContext, permissionDecision.
    """

    def __init__(
        self,
        config_path: Path | None = None,
        *,
        require_trust: bool | None = None,
        workdir: Path | None = None,
    ):
        self._workdir = workdir or BASE_DIR
        self._require_trust = (
            require_trust
            if require_trust is not None
            else os.environ.get("AGENT_HOOKS_REQUIRE_TRUST", "").strip().lower()
            in ("1", "true", "yes", "on")
        )
        self.hooks: dict[str, list[dict[str, Any]]] = {
            event: [] for event in HOOK_EVENTS
        }
        config_path = config_path or DEFAULT_CONFIG_PATH
        if config_path.exists():
            try:
                config = json.loads(config_path.read_text(encoding="utf-8"))
                hook_map = config.get("hooks", {})
                for event in HOOK_EVENTS:
                    self.hooks[event] = list(hook_map.get(event, []))
                log_event(
                    _log,
                    logging.INFO,
                    "hooks_loaded",
                    path=str(config_path),
                    counts={e: len(self.hooks[e]) for e in HOOK_EVENTS},
                )
            except Exception as e:
                log_event(
                    _log,
                    logging.WARNING,
                    "hooks_config_error",
                    path=str(config_path),
                    error=str(e),
                )

    def _workspace_trusted(self) -> bool:
        if not self._require_trust:
            return True
        return TRUST_MARKER.exists()

    def run_hooks(self, event: str, context: dict[str, Any] | None = None) -> HookResult:
        result = HookResult()
        if not self._workspace_trusted():
            log_event(_log, logging.DEBUG, "hooks_skipped_untrusted", hook_event=event)
            return result

        context = dict(context or {})
        for hook_def in self.hooks.get(event, []):
            matcher = hook_def.get("matcher")
            if matcher:
                tool_name = context.get("tool_name", "")
                if matcher != "*" and matcher != tool_name:
                    continue

            command = hook_def.get("command", "")
            if not command:
                continue

            env = dict(os.environ)
            env["HOOK_EVENT"] = event
            env["HOOK_TOOL_NAME"] = context.get("tool_name", "")
            env["HOOK_TOOL_INPUT"] = json.dumps(
                context.get("tool_input", {}),
                ensure_ascii=False,
            )[:10000]
            if "tool_output" in context:
                env["HOOK_TOOL_OUTPUT"] = str(context["tool_output"])[:10000]

            try:
                proc = subprocess.run(
                    command,
                    shell=True,
                    cwd=self._workdir,
                    env=env,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=HOOK_TIMEOUT,
                )
            except subprocess.TimeoutExpired:
                log_event(
                    _log,
                    logging.WARNING,
                    "hook_timeout",
                    hook_event=event,
                    timeout_s=HOOK_TIMEOUT,
                )
                continue
            except Exception as e:
                log_event(
                    _log,
                    logging.WARNING,
                    "hook_error",
                    hook_event=event,
                    error=str(e),
                )
                continue

            if proc.returncode == 0:
                if proc.stdout.strip():
                    log_event(
                        _log,
                        logging.DEBUG,
                        "hook_stdout",
                        hook_event=event,
                        preview=proc.stdout.strip()[:200],
                    )
                try:
                    hook_output = json.loads(proc.stdout)
                except (json.JSONDecodeError, TypeError):
                    hook_output = None
                if isinstance(hook_output, dict):
                    if "updatedInput" in hook_output:
                        context["tool_input"] = hook_output["updatedInput"]
                    if "additionalContext" in hook_output:
                        result.messages.append(str(hook_output["additionalContext"]))
                    if "permissionDecision" in hook_output:
                        result.permission_override = str(
                            hook_output["permissionDecision"]
                        )
                        log_event(
                            _log,
                            logging.DEBUG,
                            "hook_permission_decision",
                            hook_event=event,
                            decision=result.permission_override,
                        )
            elif proc.returncode == 1:
                result.blocked = True
                result.block_reason = proc.stderr.strip() or "Blocked by hook"
                log_event(
                    _log,
                    logging.INFO,
                    "hook_blocked",
                    hook_event=event,
                    reason=result.block_reason[:200],
                )
            elif proc.returncode == 2:
                msg = proc.stderr.strip()
                if msg:
                    result.messages.append(msg)
                    log_event(
                        _log,
                        logging.INFO,
                        "hook_inject",
                        hook_event=event,
                        message=msg[:200],
                    )

        return result

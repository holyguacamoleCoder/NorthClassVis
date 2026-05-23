from __future__ import annotations

from .approval import ApprovalHandler, CliApprovalHandler, DenyAskApprovalHandler
from .modes import (
    WRITE_TOOLS,
    CapabilityMode,
    MODE_TOOL_ALLOWLIST,
)
from .paths import (
    governance_path_denial_reason,
    is_governance_data_path,
    is_raw_dataset_path,
    is_writable_path,
    path_matches_pattern,
    raw_dataset_read_denial_reason,
    resolve_data_relative_path,
    writable_path_denial_reason,
)
from .rules import DEFAULT_RULES


class PermissionManager:
    """
    Pipeline: deny_rules -> mode_check (tool/mode only) -> allow_rules -> deny fallback
    """

    def __init__(
        self,
        mode: CapabilityMode = CapabilityMode.CONSULT,
        rules: list | None = None,
        approval: ApprovalHandler | None = None,
    ):
        self.mode = mode
        self.rules = list(rules if rules is not None else DEFAULT_RULES)
        self.approval = approval or DenyAskApprovalHandler()
        if isinstance(self.approval, CliApprovalHandler):
            self.approval.bind(self)
        self.consecutive_denials = 0
        self.max_consecutive_denials = 3

    def check(self, tool_name: str, tool_input: dict) -> dict:
        """Returns: {"behavior": "allow"|"deny"|"ask", "reason": str}"""
        tool_input = dict(tool_input or {})
        raw_path = str(tool_input.get("path") or "") if tool_input.get("path") is not None else ""
        if raw_path and tool_name in (
            "read_file",
            "write_file",
            "edit_file",
            "list_files",
        ):
            try:
                tool_input["path"] = resolve_data_relative_path(raw_path)
            except ValueError:
                return {
                    "behavior": "deny",
                    "reason": governance_path_denial_reason(raw_path),
                }
            if is_governance_data_path(raw_path):
                return {
                    "behavior": "deny",
                    "reason": governance_path_denial_reason(raw_path),
                }

        path_for_policy = str(tool_input.get("path") or "")

        if (
            tool_name == "read_file"
            and path_for_policy
            and is_raw_dataset_path(path_for_policy)
        ):
            return {
                "behavior": "deny",
                "reason": raw_dataset_read_denial_reason(self.mode.value),
            }

        for rule in self.rules:
            if rule.get("behavior") != "deny":
                continue
            if self._matches(rule, tool_name, tool_input):
                return {
                    "behavior": "deny",
                    "reason": f"Blocked by deny rule: {rule}",
                }

        mode_decision = self._mode_check(tool_name)
        if mode_decision is not None:
            return mode_decision

        for rule in self.rules:
            if rule.get("behavior") != "allow":
                continue
            if self._matches(rule, tool_name, tool_input):
                self.consecutive_denials = 0
                return {
                    "behavior": "allow",
                    "reason": f"Matched allow rule: {rule}",
                }

        write_fallback = self._produce_write_fallback(tool_name, tool_input)
        if write_fallback is not None:
            return write_fallback

        if tool_name in MODE_TOOL_ALLOWLIST.get(self.mode, frozenset()):
            return {
                "behavior": "ask",
                "reason": (
                    f"No rule matched for {tool_name} in {self.mode.value} mode; "
                    "approval required"
                ),
            }

        return {
            "behavior": "deny",
            "reason": f"Tool {tool_name} not in {self.mode.value} allowlist",
        }

    def remember_allow(self, tool_name: str, tool_input: dict) -> None:
        path = tool_input.get("path")
        rule = {"tool": tool_name, "behavior": "allow"}
        if path:
            rule["path"] = str(path)
        else:
            rule["path"] = "*"
        self.rules.append(rule)

    def ask_user(self, tool_name: str, tool_input: dict, reason: str) -> bool:
        raw = self.approval.approve(tool_name, tool_input, reason)
        if isinstance(raw, tuple):
            approved, remember = raw
        else:
            approved, remember = bool(raw), False

        if approved and remember:
            self.remember_allow(tool_name, tool_input)
            print(f"  [Permission] Always allow added: {tool_name} {tool_input.get('path', '*')}")

        if approved:
            self.consecutive_denials = 0
            return True

        self.consecutive_denials += 1
        if self.consecutive_denials >= self.max_consecutive_denials:
            print(
                f"  [{self.consecutive_denials} consecutive denials — "
                f"consider switching to a higher capability mode]"
            )
        return False

    def _mode_check(self, tool_name: str) -> dict | None:
        allowed = MODE_TOOL_ALLOWLIST.get(self.mode, frozenset())
        if tool_name not in allowed:
            return {
                "behavior": "deny",
                "reason": f"{self.mode.value}: tool {tool_name} not allowed",
            }

        if self.mode != CapabilityMode.PRODUCE and tool_name in WRITE_TOOLS:
            return {
                "behavior": "deny",
                "reason": f"{self.mode.value}: write operations are blocked",
            }

        if tool_name in MODE_TOOL_ALLOWLIST[self.mode] - WRITE_TOOLS:
            return {"behavior": "allow", "reason": f"{self.mode.value}: tool allowed"}

        if tool_name in WRITE_TOOLS and self.mode == CapabilityMode.PRODUCE:
            return None

        return None

    def _produce_write_fallback(self, tool_name: str, tool_input: dict) -> dict | None:
        if self.mode != CapabilityMode.PRODUCE or tool_name not in WRITE_TOOLS:
            return None
        path = tool_input.get("path", "")
        if is_writable_path(path):
            return None
        return {
            "behavior": "deny",
            "reason": writable_path_denial_reason(path),
        }

    def _matches(self, rule: dict, tool_name: str, tool_input: dict) -> bool:
        rule_tool = rule.get("tool")
        if rule_tool and rule_tool != "*" and rule_tool != tool_name:
            return False

        rule_path = rule.get("path")
        if rule_path and rule_path != "*":
            path = tool_input.get("path", "")
            if not path_matches_pattern(path, rule_path):
                return False

        rule_content = rule.get("content")
        if rule_content:
            command = tool_input.get("command", "")
            if not path_matches_pattern(command, rule_content):
                return False

        return True

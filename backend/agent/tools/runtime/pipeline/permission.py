from typing import TYPE_CHECKING, Any

from permission import PermissionManager
from permission.modes import MODE_TOOL_ALLOWLIST

from ...definitions.registry import TOOL_DISPATCHER
from .hooks import prepend_hook_messages

if TYPE_CHECKING:
    from hooks import HookManager


def allowed_tool_names(permission: PermissionManager | None) -> frozenset[str]:
    if permission is not None:
        return MODE_TOOL_ALLOWLIST.get(permission.mode, frozenset())
    return frozenset(TOOL_DISPATCHER)


def permission_denied_content(
    *,
    hooks: "HookManager | None",
    permission: PermissionManager | None,
    tool_name: str | None,
    parsed_args: dict[str, Any],
    reason: str,
    pre_messages: list[str],
    deny_type: str = "policy",
    message_prefix: str = "Permission denied",
) -> str:
    base = f"{message_prefix}: {reason}"
    if hooks is None:
        return prepend_hook_messages(base, pre_messages)

    mode = ""
    if permission is not None:
        mode = getattr(permission.mode, "value", permission.mode)
        if not isinstance(mode, str):
            mode = str(mode)

    deny_result = hooks.run_hooks(
        "PermissionDeny",
        {
            "tool_name": tool_name or "",
            "tool_input": dict(parsed_args),
            "deny_reason": reason,
            "permission_mode": mode,
            "deny_type": deny_type,
        },
    )
    hook_messages = list(deny_result.messages)
    if deny_result.blocked and deny_result.block_reason:
        hook_messages.append(deny_result.block_reason)
    return prepend_hook_messages(base, pre_messages + hook_messages)

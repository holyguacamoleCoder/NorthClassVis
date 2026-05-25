"""User-initiated turn cancellation for HTTP jobs and AgentLoop."""


class TurnCancelled(Exception):
    """Raised when the client requests stop for the in-flight user turn."""

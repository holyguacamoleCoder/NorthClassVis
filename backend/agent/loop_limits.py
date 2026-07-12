"""Configurable limits for AgentLoop (env overrides)."""

from __future__ import annotations

import os

MAX_TURNS_PER_USER_ROUND = max(4, int(os.environ.get("AGENT_MAX_TURNS_PER_ROUND", "30")))
REPORT_VALIDATE_LOOP_WINDOW = max(2, int(os.environ.get("AGENT_REPORT_VALIDATE_LOOP_WINDOW", "3")))
REPORT_POLISH_LOOP_WINDOW = max(2, int(os.environ.get("AGENT_REPORT_POLISH_LOOP_WINDOW", "3")))
AGGREGATE_RETRY_LOOP_WINDOW = max(2, int(os.environ.get("AGENT_AGGREGATE_RETRY_LOOP_WINDOW", "3")))
REPEATED_QUERY_LOOP_WINDOW = max(3, int(os.environ.get("AGENT_REPEATED_QUERY_LOOP_WINDOW", "5")))
REPEATED_QUERY_THRESHOLD = max(2, int(os.environ.get("AGENT_REPEATED_QUERY_THRESHOLD", "3")))

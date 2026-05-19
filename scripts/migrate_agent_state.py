#!/usr/bin/env python3
"""One-shot migration: data/.sessions etc. → .agent/ (safe to run multiple times)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AGENT_DIR = ROOT / "backend" / "agent"
if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))

from common.paths import (  # noqa: E402
    AGENT_STATE_DIR,
    bootstrap_agent_paths,
    migrate_legacy_agent_state,
)


def main() -> int:
    import common.paths as paths_mod

    paths_mod._bootstrapped = False
    bootstrap_agent_paths(migrate=False)
    moved = migrate_legacy_agent_state()
    print(f"Agent state root: {AGENT_STATE_DIR}")
    if moved:
        print("Relocated:")
        for line in moved:
            print(f"  - {line}")
    else:
        print("Nothing to relocate (already on .agent/ or empty legacy dirs).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

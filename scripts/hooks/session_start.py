#!/usr/bin/env python3
"""SessionStart: inject data catalog summary into the agent session context."""

from __future__ import annotations

import json
import sys

from _lib import DATA_CATALOG, ROOT

POLICY = (
    "Analysis policy: use paths under data/ (e.g. reports/foo.md, Data_StudentInfo.csv). "
    "Prefer read_file with a limit on large Data_*.csv files. "
    "Do not modify raw Data_*.csv; write outputs to data/reports/ or data/exports/ in produce mode."
)


def build_context() -> str:
    parts: list[str] = []
    if DATA_CATALOG.is_file():
        text = DATA_CATALOG.read_text(encoding="utf-8")
        if len(text) > 4500:
            text = text[:4500] + "\n\n...(catalog truncated for session context)"
        parts.append("# Data catalog\n\n" + text.strip())
    else:
        parts.append(
            "# Data catalog\n\n"
            f"(missing {DATA_CATALOG.relative_to(ROOT).as_posix()}; "
            "use list_files and read_file to explore data/)"
        )
    parts.append("\n# " + POLICY)
    return "\n".join(parts)


def main() -> None:
    payload = {"additionalContext": build_context()}
    sys.stdout.write(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()

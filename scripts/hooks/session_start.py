#!/usr/bin/env python3
"""SessionStart: inject data catalog summary into the agent session context."""

from __future__ import annotations

from _lib import DATA_CATALOG, ROOT, write_json_stdout

POLICY = (
    "Analysis policy: paths are relative to data/ (e.g. reports/foo.md, Data_StudentInfo.csv, "
    "Data_SubmitRecord/SubmitRecord-Class1.csv). "
    "Catalog source of truth: meta/data_catalog.md (injected summary below; not a report deliverable). "
    "Use read_file with limit on Data_*.csv and Data_SubmitRecord/*.csv. "
    "Do not modify raw datasets; write outputs only to reports/ or exports/ in produce mode."
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
    write_json_stdout(payload)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""CLI: validate reports/*.md against data/meta/report_quality_rules.yaml."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
AGENT_ROOT = REPO_ROOT / "backend" / "agent"
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))

import runtime_bootstrap  # noqa: E402

from report.validate import validate_report_file  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a report Markdown file.")
    parser.add_argument("--file", "-f", required=True, help="Path to report .md")
    parser.add_argument(
        "--tier",
        "-t",
        choices=["student", "class", "major", "freeform"],
        help="Report tier (default: infer from path)",
    )
    parser.add_argument("--json", action="store_true", help="Print full JSON result")
    parser.add_argument(
        "--require-cites",
        action="store_true",
        help="Warn if Evidence has no [@ds|ref:…] tags",
    )
    args = parser.parse_args()

    path = Path(args.file)
    if not path.is_file():
        print(f"Error: file not found: {path}", file=sys.stderr)
        return 2

    result = validate_report_file(
        path,
        tier=args.tier,
        require_evidence_cites=args.require_cites,
    )

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        status = "OK" if result.get("ok") else "FAIL"
        print(f"{status} tier={result.get('tier')} lines={result.get('line_count')}")
        for err in result.get("errors") or []:
            print(f"  error: {err}")
        for warn in result.get("warnings") or []:
            print(f"  warn: {warn}")

    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Resolve real Class1 student / knowledge IDs into fixtures/entities.json."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path

AGENT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[3]

_VALID_STUDENT_ID_RE = re.compile(r"^[0-9a-f]{16,24}$", re.I)


def is_valid_student_id(value: str) -> bool:
    return bool(_VALID_STUDENT_ID_RE.match(str(value or "").strip()))

DEFAULT_OUT = Path(__file__).resolve().parent / "fixtures" / "entities.json"
SUBMIT_CSV = REPO_ROOT / "data" / "Data_SubmitRecord" / "SubmitRecord-Class1.csv"
TITLE_CSV = REPO_ROOT / "data" / "Data_TitleInfo.csv"
REPORT_REL = "reports/eval/class1_week_draft.md"
REPORT_ABS = REPO_ROOT / "data" / REPORT_REL


def _top_student_ids(path: Path, n: int = 3) -> list[str]:
    with path.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    if not rows or "student_ID" not in rows[0]:
        raise RuntimeError(f"no student_ID column in {path}")
    counts = Counter(
        str(r["student_ID"]).strip()
        for r in rows
        if is_valid_student_id(str(r.get("student_ID") or ""))
    )
    if len(counts) < n:
        raise RuntimeError(f"need >= {n} real student_IDs in {path}, got {len(counts)}")
    return [sid for sid, _ in counts.most_common(n)]


def _top_knowledge_ids(path: Path, n: int = 2) -> list[str]:
    with path.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    if not rows or "knowledge" not in rows[0]:
        raise RuntimeError(f"no knowledge column in {path}")
    counts = Counter(
        str(r["knowledge"]).strip()
        for r in rows
        if str(r.get("knowledge") or "").strip() and "_" not in str(r["knowledge"])
    )
    if len(counts) < n:
        # Fall back to any non-empty knowledge codes.
        counts = Counter(
            str(r["knowledge"]).strip() for r in rows if str(r.get("knowledge") or "").strip()
        )
    if len(counts) < n:
        raise RuntimeError(f"need >= {n} knowledge values in {path}, got {len(counts)}")
    return [k for k, _ in counts.most_common(n)]


def _ensure_report_fixture() -> None:
    REPORT_ABS.parent.mkdir(parents=True, exist_ok=True)
    if REPORT_ABS.is_file():
        return
    REPORT_ABS.write_text(
        "# Class1 周报草稿（eval fixture）\n\n"
        "## scope\n\nClass1。\n\n"
        "## summary\n\n占位草稿，供 scope 附件 hint 使用。\n",
        encoding="utf-8",
    )


def resolve(*, class_name: str = "Class1", out: Path = DEFAULT_OUT) -> dict:
    submit = REPO_ROOT / "data" / "Data_SubmitRecord" / f"SubmitRecord-{class_name}.csv"
    if not submit.is_file():
        raise FileNotFoundError(f"missing submit CSV: {submit}")
    if not TITLE_CSV.is_file():
        raise FileNotFoundError(f"missing title CSV: {TITLE_CSV}")

    student_ids = _top_student_ids(submit, 3)
    knowledge_ids = _top_knowledge_ids(TITLE_CSV, 2)
    _ensure_report_fixture()

    payload = {
        "class": class_name,
        "student_ids": student_ids,
        "knowledge_ids": knowledge_ids,
        "knowledge_labels": list(knowledge_ids),
        "report_path": REPORT_REL,
        "report_label": "班级周报草稿",
        "source": f"resolved_from_{class_name}_csv",
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Resolve Class1 entities for agent benchmark")
    p.add_argument("--class-name", default="Class1")
    p.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = p.parse_args(argv)
    try:
        payload = resolve(class_name=args.class_name, out=args.out)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    print(f"Wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

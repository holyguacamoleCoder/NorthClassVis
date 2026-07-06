#!/usr/bin/env python3
"""Offline enrichment: add week_index to SubmitRecord-Class*.csv files.

Week index matches backend/services/week_service.calculate_week_of_year:
per-class file, anchor at min(time), week = (days since anchor) // 7.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend"))

from services.week_service import calculate_week_of_year  # noqa: E402

DEFAULT_DIR = ROOT / "data" / "Data_SubmitRecord"


def compute_week_index(series: pd.Series) -> pd.Series:
    start_date = series.min()
    return series.apply(lambda value: int(calculate_week_of_year(value, start_date=start_date)))


def enrich_file(path: Path, *, dry_run: bool = False, force: bool = False) -> str:
    df = pd.read_csv(path)
    if "time" not in df.columns:
        return "no_time"

    if "week_index" in df.columns and not force:
        return "skip"

    week_index = compute_week_index(df["time"])
    cols = list(df.columns)
    if "week_index" in cols:
        df["week_index"] = week_index
    else:
        time_idx = cols.index("time")
        df.insert(time_idx + 1, "week_index", week_index)

    if not dry_run:
        df.to_csv(path, index=False)
    return "ok"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dir",
        type=Path,
        default=DEFAULT_DIR,
        help=f"Directory with SubmitRecord-Class*.csv (default: {DEFAULT_DIR})",
    )
    parser.add_argument("--dry-run", action="store_true", help="Report only; do not write files")
    parser.add_argument("--force", action="store_true", help="Recompute week_index even if column exists")
    args = parser.parse_args()

    data_dir = args.dir
    if not data_dir.is_dir():
        print(f"Directory not found: {data_dir}", file=sys.stderr)
        return 1

    paths = sorted(data_dir.glob("SubmitRecord-Class*.csv"))
    if not paths:
        print(f"No SubmitRecord-Class*.csv in {data_dir}", file=sys.stderr)
        return 1

    counts: dict[str, int] = {}
    for path in paths:
        status = enrich_file(path, dry_run=args.dry_run, force=args.force)
        counts[status] = counts.get(status, 0) + 1
        if status == "ok":
            sample = pd.read_csv(path, nrows=1)
            week_range = ""
            if not args.dry_run and "week_index" in sample.columns:
                full = pd.read_csv(path, usecols=["week_index"])
                week_range = f" week_index {int(full['week_index'].min())}-{int(full['week_index'].max())}"
            prefix = "[dry-run] " if args.dry_run else ""
            print(f"{prefix}{path.name}: enriched{week_range}")
        elif status == "skip":
            print(f"{path.name}: skipped (week_index exists, use --force to recompute)")
        else:
            print(f"{path.name}: {status}")

    print(
        f"Done: {counts.get('ok', 0)} enriched, "
        f"{counts.get('skip', 0)} skipped, "
        f"{counts.get('no_time', 0)} missing time"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

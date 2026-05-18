---
name: report-markdown
description: Generate structured Markdown reports under data/reports/
---

# Report Markdown Skill

Use this skill when the user asks for a report, summary, or documentation of data files or analysis results.

## Paths

- All tool paths are relative to `data/` (e.g. `reports/topic/summary.md`).
- Write outputs only to `reports/` or `exports/` (produce mode required for writes).
- Never modify raw `Data_*.csv` files.

## Workflow

1. Use session context (catalog summary from `meta/data_catalog.md`) or `read_file("meta/data_catalog.md", limit=80)` for full schema; use `list_files` to list `Data_SubmitRecord/` classes.
2. Use `read_file` with a `limit` on large CSV files to sample schema and rows.
3. Use `todo_write` for multi-section reports.
4. Write the final report with `write_file` to a clear path such as `reports/<topic>/summary.md`.

## Report structure

```markdown
# <Title>

## Overview
Brief purpose and data sources used.

## Data sources
For each file: format, fields (table or list), constraints.

## Findings
Analysis or structure notes.

## Limitations
Sampling, encoding issues, or missing data.

---
Generated for NorthClassVision data workspace.
```

## Quality

- Use complete sentences; avoid telegraphic bullet-only sections.
- Cite actual column names from CSV headers when describing schemas.
- Prefer nested folders for multi-session work: `reports/session1/chapter1/summary.md`.

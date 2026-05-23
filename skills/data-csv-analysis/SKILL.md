---
name: data-csv-analysis
description: Explore and analyze academic datasets via logical resources (inspect_schema / query_data / aggregate_data)
---

# Data Analysis Skill (resource-based)

Use for **student / title / submit-record** exploration and statistics.

## Modes

| Mode | Tools for tabular data |
|------|-------------------------|
| consult | `inspect_schema` only (columns, samples, row count) |
| analyze | `inspect_schema` → `query_data` → `aggregate_data`；可选 `list_datasets` 查 catalog |
| produce | same as analyze + write reports |

**Do not** `read_file` raw `Data_*.csv` or `Data_SubmitRecord/*.csv` (blocked or unavailable).

## Resources

- `student_info`, `title_info` — no class filter
- `submit_record` — **single entry for submission analysis** (already joined with title + student columns)
  - Required: `class="Class1"` **or** `classes=["Class1"]`
  - Optional: `majors=["J23517"]` for major filter
- `week_aggregation` — weekly trend series; needs `classes`

Full registry: `data/meta/resource_registry.yaml`. SessionStart injects `meta/data_catalog.md` summary.

## Field rules (avoid empty results)

- **Major codes** (e.g. `J23517`) → filter with `majors=[...]` or `where.field="major"`.
- **Never** put a major code in `student_ID` — that field is a long hash-like id, not a major.
- Use **`where`**, not `filter` (unknown keys are ignored).

---

## Workflow P — Plan then compute (multi-step / 先规划再计算)

When the teacher asks for **several metrics** or says to plan first:

1. **`todo_write`** — 3–5 steps; each item has `acceptance` (verifiable, e.g. `count_distinct student_ID by major, no warnings`).
2. Only **one** item `in_progress` at a time.
3. **`query_data`** — omit `limit` for full scans; **never** `limit: 0` (rejected). For enrollment + scores, `select: ["major", "student_ID", "score"]` on `submit_record` + `class`.
4. **`aggregate_data`** — one call with all metrics, e.g. `count_distinct` on `student_ID` by `dimensions: ["major"]`, plus `mean` on `score`.
5. **`todo_write`** again — mark step `completed` only if `meta.warnings` is empty; else fix query and retry.
6. Final answer only when all items are `completed`.

### Enrollment by major (Class1)

Question: *各专业选课人数（学生数）*

```json
{
  "resource": "submit_record",
  "class": "Class1",
  "select": ["major", "student_ID"]
}
```

```json
{
  "input": {"result_ref": "<ref>"},
  "dimensions": ["major"],
  "metrics": [{"op": "count_distinct", "field": "student_ID", "as": "students"}]
}
```

`count` without `count_distinct` counts **submission rows**, not students.

---

## Workflow A — Statistics only (count / mean / min / max)

When the teacher asks **how many** or **average / total** (no row preview needed):

**Exactly 2 tool calls — do not parallelize duplicates.**

1. **One** `query_data` with only the columns needed for metrics:

```json
{
  "resource": "submit_record",
  "class": "Class1",
  "majors": ["J23517"],
  "select": ["score"]
}
```

- **Omit `limit` for full statistics** (required for correct mean/count). Do not pass `limit: 0` (rejected).
- **Do not** issue a second `query_data` with the same `class` / `classes` / `majors` / `where` — even with different `select`. One query is enough.

2. **One** `aggregate_data` on that single `result_ref`:

```json
{
  "input": {"result_ref": "<from query meta.result_ref>"},
  "metrics": [
    {"op": "count", "as": "n"},
    {"op": "mean", "field": "score", "as": "avg_score"}
  ]
}
```

- Put **all** needed metrics in **one** `metrics` array. Do not call `aggregate_data` twice on the same `result_ref` with different `as` names for the same ops.

3. Answer from the aggregate JSON. No extra query unless the teacher asks for a different filter or breakdown.

### Example (matches common teacher questions)

Question: *Class1 里，专业 J23517 的学生提交了多少条？平均分多少？*

```
query_data(resource=submit_record, class=Class1, majors=[J23517], select=[score])
  → meta.result_ref
aggregate_data(input={result_ref}, metrics=[count, mean(score)])
  → answer n and avg_score
```

**Wrong (wasteful):** two parallel `query_data` (full columns + select score), then two parallel `aggregate_data` on two refs.

---

## Workflow B — Explore first, then statistics

When columns or filters are **uncertain**:

1. `inspect_schema(resource="submit_record", class="Class1")` — confirm `major`, `score`, etc.
2. One `query_data` (add `where` / `majors` as needed).
3. One `aggregate_data` if metrics are required.

Skip `inspect_schema` when the question is a straightforward count/mean on known fields (`score`, `major`, `class`).

---

## Workflow C — Preview / export / ranked lists

When the teacher wants **sample rows**, top-N, or export — not just a single number:

1. `query_data` with `select`, `where`, `order_by`, `limit` as needed.
2. Use returned preview `rows` directly, or `meta.result_ref` for large results.
3. Call `aggregate_data` **only if** rollups are still needed.

---

## query_data parameters

| Param | Notes |
|-------|--------|
| `class` / `classes` | Required for `submit_record`. `class="Class1"` is fine; auto-normalized to `classes`. |
| `majors` | Optional major filter on `submit_record`. |
| `select` | For stats, list only metric fields (e.g. `["score"]`). Omit for wide previews. |
| `where` | DSL: `{op, field, value}` or `{op: "and", conditions: [...]}`. |
| `limit` | Optional preview cap (≥1). **Omit for full matching set when aggregating.** `limit: 0` is rejected. |

Each `query_data` returns **`meta.result_ref`** and **`meta.dataset_id`** (catalog on disk). Binding rules:

| Teacher intent | What to do |
|----------------|------------|
| Summarize **these N rows** (same turn) | `bind="chain"` or `input.chain_from_dataset_id` / that query's `dataset_id` |
| **Class-wide** stats (new question or new scope) | New `query_data` **without** `limit`, then aggregate; `bind="fresh"` |
| Reuse an earlier slice **on purpose** | `input.dataset_id` from that query (cross-turn OK when explicit) |

Do **not** reuse a prior turn's `result_ref` without `dataset_id`. Runtime rejects implicit cross-turn binding.

Forgot which `dataset_id` to use? Call **`list_datasets`** or **`resolve_dataset_binding`** before `aggregate_data`.  
Runtime also runs **semantic binding** (teacher message + catalog) when slice vs full class is ambiguous.

When the teacher asks **「这些记录」**, chain to the slice dataset; for **全班概况**, run a fresh full query first.

---

## aggregate_data parameters

- **Required**: `input` with `result_ref`, `dataset_id`, or `chain_from_dataset_id` from `query_data`; or inline `{schema, rows}` for tiny tables.
- Optional **`bind`**: `chain` | `fresh` | `auto` (default).
- **Required**: `metrics` — combine count + mean + min/max in **one** call when possible.
- `count` = row count; **`count_distinct`** = unique values (e.g. students via `student_ID`).
- `count` does not require `field`; `count_distinct` / `mean` / `sum` / `min` / `max` need `field`.
- Read `meta.warnings` and `[Checks]` footer before answering.
- Prefer explicit `query_data` first; do not rely on implicit auto-query unless you accept extra latency.

---

## Anti-patterns (do not do these)

| Anti-pattern | Why |
|--------------|-----|
| Parallel two `query_data` with same filter | Doubles scan; **full + limit** parallel → aggregate picks wrong ref |
| Parallel `limit=10` + full `submit_record` | Wasteful; use one query, or `bind=chain` vs `fresh` explicitly |
| Parallel two `aggregate_data` on refs from duplicate queries | Same numbers twice (`submission_count` vs `score_count`) |
| `student_ID eq "J23517"` | J23517 is a major code → use `majors` or `where.major` |
| `inspect_schema` before every simple count/mean | Extra turn; skip when fields are obvious |
| `read_file` on `Data_*.csv` | Blocked; use logical resources |
| `count` for 选课人数 | Use `count_distinct` on `student_ID` |
| `student_info` + `classes` only | No class column; use `submit_record` for Class1 |
| `limit: 0` or aggregate on truncated ref | Empty/wrong stats; omit limit, fix warnings |

---

## Reports (produce mode)

After analyze workflow, write markdown/JSON under `reports/` or `exports/` with conclusions backed by aggregate results.

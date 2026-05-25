---
name: data-exploration
description: 学业逻辑 resource 探查与统计（inspect_schema / query_data / aggregate_data 完整工作流）
---

# Data Exploration Skill (resource-based)

由 `data-csv-analysis` 演进；**本 skill 为完整正文**。旧名 `data-csv-analysis` 仍 `load_skill` 可得迁移提示。

用于 **student / title / submit-record** 探索与统计（不限报告粒度）。

## Modes

| Mode | Tools for tabular data |
|------|-------------------------|
| consult | `inspect_schema` only (columns, samples, row count) |
| analyze | `inspect_schema` → `query_data` → `aggregate_data`；可选 `list_datasets` |
| produce | same as analyze + write reports |

**Do not** `read_file` raw `Data_*.csv` or `Data_SubmitRecord/*.csv`.

## Resources

- `student_info`, `title_info` — no class filter
- `submit_record` — **single entry** (joined title + student)
  - Required: `class="Class1"` **or** `classes=["Class1"]`
  - Optional: `majors=["J23517"]`
- `week_aggregation` — weekly trend; needs `classes`

Registry: `data/meta/resource_registry.yaml`. SessionStart injects `meta/data_catalog.md` summary.

## Field rules

- **Major codes** → `majors=[...]` or `where.field="major"`.
- **Never** put major code in `student_ID`.
- Use **`where`**, not `filter`.

---

## Workflow P — Plan then compute

1. **`todo_write`** — 3–5 steps with `acceptance`.
2. One `in_progress` at a time.
3. **`query_data`** — omit `limit` for full scans; never `limit: 0`.
4. **`aggregate_data`** — one call, all metrics.
5. **`todo_write`** — complete only if `meta.warnings` empty.

### Enrollment by major (Class1)

```json
{"resource": "submit_record", "class": "Class1", "select": ["major", "student_ID"]}
```

```json
{
  "input": {"result_ref": "<ref>"},
  "dimensions": ["major"],
  "metrics": [{"op": "count_distinct", "field": "student_ID", "as": "students"}]
}
```

---

## Workflow A — Statistics only

**Exactly 2 tool calls.**

1. One `query_data` with metric columns only; omit `limit` for full stats.
2. One `aggregate_data` on that `result_ref`.

---

## Workflow B — Explore first

1. `inspect_schema` when columns uncertain.
2. One `query_data`.
3. One `aggregate_data` if needed.

---

## Workflow C — Preview / ranked lists

`query_data` with `limit` / `order_by`; aggregate only if rollups needed.

---

## query_data parameters

| Param | Notes |
|-------|--------|
| `class` / `classes` | Required for `submit_record` |
| `majors` | Optional major filter |
| `select` | Stats: only metric fields |
| `where` | DSL conditions |
| `limit` | Preview only; omit when aggregating |

Binding: `bind=chain` vs `fresh` vs `dataset_id` — see session catalog. 「这些记录」→ chain；「全班概况」→ fresh full query.

---

## aggregate_data parameters

- `input`: `result_ref`, `dataset_id`, or `chain_from_dataset_id`
- `metrics`: combine in one call when possible
- `count_distinct` for 选课人数；`count` = 提交行数

---

## Anti-patterns

| Anti-pattern | Why |
|--------------|-----|
| Parallel duplicate `query_data` | Wrong ref for aggregate |
| `student_ID eq "J23517"` | Use `majors` |
| `read_file` on `Data_*.csv` | Use resources |
| `count` for 选课人数 | Use `count_distinct` |
| `limit: 0` | Rejected |

---

## 与 tiered 报告的关系

- 探查/统计：本 skill
- 个体/班/专业 **正式章节**：先 `analysis-student` / `analysis-class` / `analysis-major`，再 `tiered-report`

---
name: data-exploration
description: 逻辑 resource 探查与统计（inspect_schema、query_data、aggregate_data）；字段不明、选课人数、预览榜单。勿用于正式 diagnosis/overview（produce 改 load analysis-*）。
---

# Data Exploration（resource-based）

用于 **student / title / submit_record** 探索与统计（不限报告粒度）。

## Modes

| Mode | Tools for tabular data |
|------|-------------------------|
| consult | `inspect_schema` only |
| analyze | `inspect_schema` → `query_data` → `aggregate_data`；可选 `list_datasets` |
| produce | 同 analyze；写报告另 `load_skill` `analysis-*` |

**Do not** `read_file` raw `Data_*.csv` or `Data_SubmitRecord/*.csv`.

## Resources

- `student_info`, `title_info` — no class filter
- `submit_record` — requires `class="Class1"` **or** `classes=["Class1"]`; optional `majors`
- `week_aggregation` — needs `classes`

Registry: `data/meta/resource_registry.yaml`. SessionStart injects `meta/data_catalog.md`.

## Field rules

- Major codes → `majors=[...]` or `where.field="major"`; never in `student_ID`
- Use **`where`**, not `filter`

---

## Workflow P — Plan then compute

1. **`todo_write`** — 3–5 steps with `acceptance`
2. One `in_progress` at a time
3. **`query_data`** — omit `limit` for full scans; never `limit: 0`
4. **`aggregate_data`** — one call, all metrics
5. **`todo_write`** — complete only if `meta.warnings` empty

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

**Exactly 2 tool calls:** one `query_data` (omit `limit`) → one `aggregate_data`.

## Workflow B — Explore first

`inspect_schema` → `query_data` → `aggregate_data` if needed.

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

Binding: `bind=chain` vs `fresh` vs `dataset_id` — see session catalog.

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

## 与正式报告

- 探查/统计：本 skill
- 正式报告：`load_skill` `analysis-student` | `analysis-class` | `analysis-major`，并 `load_skill report-delivery`（`skills/reference/`）
- **勿** `read_file` `reports/` 作参考；`reports/` 仅产出写入

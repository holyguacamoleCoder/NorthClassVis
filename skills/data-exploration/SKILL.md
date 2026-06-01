---
name: data-exploration
description: 使用逻辑资源（inspect_schema/query_data/aggregate_data）进行数据探查、筛选与统计分析。当用户需要查字段、算人数/均值、做分组汇总、验证趋势结论或先分析后再写报告时使用。
---

# Data Exploration（resource-based）

用于 `student` / `title` / `submit_record` 探索与统计（不限报告粒度）。

## Modes

| Mode | Tools for tabular data |
|------|-------------------------|
| consult | `inspect_schema` only |
| analyze | `inspect_schema` -> `query_data` -> `aggregate_data`；可选 `list_datasets` |
| produce | 同 analyze；写报告改用 `report-writing` |

Do not `read_file` raw `Data_*.csv` or `Data_SubmitRecord/*.csv`.

## Resources

- `student_info`, `title_info` - no class filter
- `submit_record` - requires `class="Class1"` or `classes=["Class1"]`; optional `majors`
- `week_aggregation` - needs `classes`

Registry: `data/meta/resource_registry.yaml`. SessionStart injects `meta/data_catalog.md`.

## Field rules

- Major codes -> `majors=[...]` or `where.field="major"`; never in `student_ID`
- Use `where`, not `filter`

## Week-range analysis (e.g. weeks 13–15)

Use **`week_aggregation`**, not `submit_record` (`submit_record` has no `week` column).

Preferred — resolve param:

```json
{"resource": "week_aggregation", "classes": ["Class2"], "week_range": [13, 15]}
```

Alternative — `where` on `week_index` (alias `week` is accepted):

```json
{
  "resource": "week_aggregation",
  "classes": ["Class2"],
  "where": {
    "op": "and",
    "conditions": [
      {"field": "week_index", "op": "gte", "value": 13},
      {"field": "week_index", "op": "lte", "value": 15}
    ]
  }
}
```

Metrics: `mean(peak_value)` by `week_index`; use `count_distinct(student_ID)` for participation.

## Workflow P — Plan then compute

1. `todo_write` - 3 to 5 steps with `acceptance`
2. One `in_progress` at a time
3. `query_data` - omit `limit` for full scans; never `limit: 0`
4. `aggregate_data` - one call, all metrics
5. `todo_write` - complete only if `meta.warnings` empty

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

## Workflow A — Statistics only

Exactly 2 tool calls: one `query_data` (omit `limit`) -> one `aggregate_data`.

## Workflow B — Explore first

`inspect_schema` -> `query_data` -> `aggregate_data` if needed.

## Workflow C — Preview / ranked lists

`query_data` with `limit` / `order_by`; aggregate only if rollups needed.

## aggregate_data parameters

- `input`: `result_ref`, `dataset_id`, or `chain_from_dataset_id`
- `metrics`: combine in one call when possible
- `count_distinct` for 选课人数；`count` = 提交行数

## Anti-patterns

| Anti-pattern | Why |
|--------------|-----|
| Parallel duplicate `query_data` | Wrong ref for aggregate |
| `student_ID eq "J23517"` | Use `majors` |
| `read_file` on `Data_*.csv` | Use resources |
| `count` for 选课人数 | Use `count_distinct` |
| `limit: 0` | Rejected |

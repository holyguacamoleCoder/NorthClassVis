# Report Writing — Shared Rules

> 各粒度细则见 `load_reference(student|class|major|freeform)`。本章为全报告通用规则。

## report-chart 语法

```report-chart
{
  "view": "WeekView",
  "params": {
    "student_ids": ["<student_ID>"],
    "week_range": [13, 15]
  }
}
```

- params 必须与本轮 `build_visual_links` **完全一致**（先 build，再写入报告）
- **禁止** `![说明](<report-chart>{...})` 或 `(<report-chart>{...})`；只用上方 fence 块
- fence **内只能有 JSON**，说明文字写在 ` ``` ` 闭合**之后**（写进 fence 会报 `Extra data` 解析错误）
- 全文 **WeekView report-chart ≤ 1**
- **StudentView 禁止** report-chart（仅用 `build_visual_links`）
- 每个 chart 下方 **至少 2 句**解释，说明图表支撑哪条结论

契约：`data/meta/report_chart_protocol.yaml`、`visual_link_contract.yaml`

## Evidence 与引用标签

`## Evidence` 只列**支撑结论**的数据来源，使用引用标签：

- `[@ds:<dataset_id>]` — 来自 `list_datasets` / `aggregate_data` 链
- `[@ref:query-results/<file>.json]` — 来自 `query_data` 的 `result_ref`
- 可选摘要：`[@ds:abc123 班级周均 peak，week 13–15]`

**禁止** Markdown 链接写法 `[说明](query-results/…)`；校验会报错，须改为 `[@ref:…]`。

禁止：无标签的「见上文」；禁止引用 `load_skill`、`todo_write`；禁止旧会话或 `reports/` 历史稿。

## 写作原则

1. 先结论后证据
2. 只写数据支持的事实；区分观察与推测
3. 禁止无依据推断学习态度/心理（如「不认真」「缺乏兴趣」）
4. 教学建议格式：**发现 → 证据 → 建议**

## 写后自检

- [ ] `write_file`/`edit_file` 后查看 tool result 中 `[Report validate]`，有 error 须 `edit_file` 修复（error 时工具会标为失败并附 reminder）
- [ ] 写完报告会自动打开 **预览**；`build_visual_links` 的图块会尽量自动写入报告（`report-chart`）
- [ ] 必填 `##` 章节齐全（tier reference + validate 输出）
- [ ] Evidence 含 cite 标签
- [ ] 每个 report-chart 有正文解释

本地校验：`py -3.11 scripts/validate_report.py --tier <tier> --file <path>`

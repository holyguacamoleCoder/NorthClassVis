---
name: report-markdown
description: [已迁移] 请 load tiered-report；本条目保留别名兼容
---

# 已迁移 → `tiered-report`

正式学业报告骨架（student / class / major 三套 `##` 章节与路径规范）已迁至：

**`load_skill("tiered-report")`**

## 别名要点

- 路径相对 `data/`；仅写 `reports/`、`exports/`
- 写报告前先 `load_skill` 对应 `analysis-*`（流程），再 `tiered-report`（模板）
- 勿改 `Data_*.csv`

通用 Markdown 质量：完整句子、引用真实字段名、Limitations 写明抽样与 warnings。

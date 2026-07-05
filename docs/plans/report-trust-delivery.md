# 报告可信交付与 Skills 瘦身 — 实施计划

> 分支：`feat/report-trust-delivery`  
> 来源：Skills 编写评审 + 长文/可交互图/证据可追溯设计讨论（2026-07）  
> 状态：进行中

## 背景与目标

### 现状问题

1. **Skills 臃肿**：`report-writing/SKILL.md` 与 4 个 `references/*.md` 大量重复（图表约束、Evidence/Limitations、写作禁令）；`load_reference` pin 全文时 token 浪费严重。
2. **报告偏短**：平均约 50 行，缺少「厚报告 + 嵌入式交互图」的交付标准（目标约 120–180 行）。
3. **无写后校验**：章节缺失、篇幅不足、`report-chart` 与 `build_visual_links` 不一致时无自动反馈。
4. **证据不可验真**：HTTP `evidence` 实为 `trace.steps` 的工具摘要，与正文 `## Evidence` 未绑定；过程轨迹与交付物验真混用。
5. **断链**：`SKILL.md` 列出 `references/mixed.md` 但文件不存在。

### 总目标

| 维度 | 目标 |
|------|------|
| 交付物 | 长文 Markdown + `report-chart` 可交互图；分章 `write_file` / `edit_file` 续写 |
| 质量 | 写后自动校验（结构 / 篇幅 / 图表 / 引用），结果回流 tool result |
| 可信 | 正文 `[@ds:…]` / `[@ref:…]` 绑定会话数据；HTTP 区分 `report_evidence` 与 `trace` |
| Skills | 薄入口 + `_shared.md` + tier delta；契约与脚本为单一事实来源 |

### 设计原则（create-skill）

- **MD**：何时写、怎么组织、定性 acceptance、示例与反模式（短表）。
- **YAML 契约**：章节 id、行数阈值、图表规则、引用标签语法。
- **Python 脚本/库**：解析、计数、对照 `result_ref`、postprocess 挂钩；CI 与 Agent 共用。

---

## 架构：三层分工

```text
data/meta/                    # 机器可读契约（可测、可调参）
  analysis_ontology.yaml      # 已有：粒度 × lens、个体章节
  visual_link_contract.yaml   # 已有：view params
  report_quality_rules.yaml   # 新建：tier 必填章、行数、表格
  report_chart_protocol.yaml  # 新建：fence 语法、per-view 限制
  evidence_cite_protocol.yaml # 新建：[@ds|ref:…] 语法

backend/agent/report/         # 校验运行时（write 后 / CLI / 测试）
  parse.py                    # ## <id> 结构解析
  charts.py                   # report-chart 提取 + validate_links
  evidence_cites.py           # 引用标签解析
  validate.py                 # 统一入口 validate_report(...)

skills/report-writing/        # Agent 写作指南（渐进披露）
  SKILL.md                    # 薄：workflow + 路由 + checklist
  references/_shared.md         # 通用图表/写作/cite 示例
  references/{student,class,major,freeform}.md  # 仅 tier delta

scripts/validate_report.py    # CLI：本地 / hooks / CI
```

**Prompt 分工**（保持不变）：

- `prompts.py`：模式边界、路由表（无 SKILL 全文）
- `load_skill` / `load_reference`：pin 全文
- `write_file` / `edit_file` postprocess：附加 `[Report validate: …]`

---

## 阶段划分

### Phase 0 — 计划与契约骨架 ✅ 本分支首批

- [x] 本文档
- [x] `report_quality_rules.yaml`
- [x] `report_chart_protocol.yaml`
- [x] `evidence_cite_protocol.yaml`
- [x] `backend/agent/report/*` + `scripts/validate_report.py`
- [x] `test/test_report_validate.py`（fixture 过/不过）
- [x] `skills/README.md` 指向本计划

**验收**：`py scripts/validate_report.py --tier student --file <fixture>` 输出结构化 JSON；pytest 绿。

### Phase 1 — 写后反馈闭环

- [ ] `postprocess.py`：`write_file` / `edit_file` 成功后对 `reports/*.md` 调用 `validate_report`
- [ ] 将 `errors` / `warnings` 追加到 tool result（Agent 可 `edit_file` 修补）
- [ ] tier 推断：路径启发式 `reports/student/` → `student` 等

**验收**：produce 写短报告后 tool result 含校验警告；补全章节后 warnings 减少。

### Phase 2 — Skills 瘦身

- [ ] 新建 `references/_shared.md`（图表、Evidence 写法、cite 示例、写后自检）
- [ ] 瘦身 `report-writing/SKILL.md`（<150 行）：workflow、scope 表、路径、checklist
- [ ] 瘦身 `student|class|major|freeform.md`（各 <120 行）：仅 Required Sections + delta
- [ ] 删除 `mixed.md` 引用或补文件
- [ ] `load_reference` 可选：tier 加载时 prepend `_shared`（需改 `references.py` / `produce_bootstrap`）

**验收**：`test_skills.py` 通过；pin token 量较现版下降（人工对比）。

### Phase 3 — 分章续写工作流

- [ ] Skill workflow：首轮 `write_file` 骨架（全部 `## <id>`）→ 分章 `edit_file`
- [ ] `validate_report` 增强：章节顺序、空章检测
- [ ] 与 `todo_write` acceptance 对齐（每章一条 todo）

**验收**：个体诊断报告按章写入，结构校验全程通过。

### Phase 4 — report-chart 强校验

- [ ] `charts.py`：对比会话内 `build_visual_links` tool results（params 一致）
- [ ] 图表下方解释行数（`require_explanation_lines_below`）
- [ ] 前后端 schema 对齐（长期：由 YAML 生成 JSON Schema）

**验收**：故意不一致的 chart params 产生 `error`；与前端 `reportCharts.js` 行为一致。

### Phase 5 — 证据引用与 HTTP 分层

- [ ] `evidence_cites.py` + `digest.py`：解析 `[@ds:…]`，对照 session `QuerySnapshot` / `result_store`
- [ ] `validate_evidence_cites`：标签存在性、ref 文件可读
- [ ] `adapter.py`：新增 `report_evidence`（可验真摘要）；`trace` 仅过程；`evidence` 字段 deprecated 或改为 `process_evidence`
- [ ] Skill：`## Evidence` 必须使用 cite 标签

**验收**：`test_agent_contract` 更新；前端可展示可核对 evidence 列表。

---

## 契约摘要

### report_quality_rules.yaml

- `tiers`: `student` | `class` | `major` | `freeform`
- 每 tier：`min_total_lines`、`required_sections[]`、`sections.<id>.min_lines`、`require_chart`、`min_table_rows`
- 全局：`required_tail_sections: [evidence, limitations]`

### report_chart_protocol.yaml

- `fence_languages: [report-chart]`（兼容 `chart` / `json`）
- `max_per_view.WeekView: 1`
- `forbid_report_chart: [StudentView]`
- `view_params` → 引用 `visual_link_contract.yaml`

### evidence_cite_protocol.yaml

- 模式：`[@ds:<dataset_id>]`、`[@ref:query-results/<file>.json]`
- 可选摘要：`[@ds:xxx 班级周均 peak，week 13–15]`
- 禁止：无标签的「见上文 query」

---

## 分章写入约定（Phase 3 起）

| 轮次 | 工具 | 内容 |
|------|------|------|
| 1 | `write_file` | 标题 + 全部 `## <id>` 占位 + `scope` / `summary` 首稿 |
| 2…n | `edit_file` | 按 ontology 顺序填充 `week_trend`、`question_anchors`… |
| 末 | `edit_file` | `evidence`（含 cite 标签）、`limitations` |

禁止：在未跑完 analyze 查询前写分析章；禁止 `read_file` 旧 `reports/`。

---

## MD vs 脚本（速查）

| 能力 | MD | 脚本/YAML |
|------|-----|-----------|
| 何时分章、写作原则 | ✅ | |
| 章节 id 枚举 | 链接 ontology | ✅ rules yaml |
| 行数/表格阈值 | 目标描述 | ✅ rules yaml |
| report-chart 语法示例 | ✅ 1–2 个 | ✅ protocol yaml |
| params 字段表 | ❌ | ✅ visual_link_contract |
| cite 写法示例 | ✅ | ✅ cite protocol |
| 解析/验真/HTTP | ❌ | ✅ Python |

---

## 测试

```bash
# 单元测试
cd backend/agent && py -3.11 -m pytest test/test_report_validate.py -q

# CLI
py scripts/validate_report.py --tier student --file path/to/report.md
py scripts/validate_report.py --tier student --file path/to/report.md --json

# 回归（skills / agent）
cd backend/agent && py -3.11 -m pytest test/test_skills.py test/test_system_prompt.py -q
```

---

## 风险与依赖

| 风险 | 缓解 |
|------|------|
| 校验过严导致 Agent 反复 edit | `error` vs `warning` 分级；阈值放 YAML 可调 |
| tier 自动推断错误 | CLI 显式 `--tier`；postprocess 用路径启发式 + warning |
| 与 `analysis_ontology.yaml` 漂移 | required_sections 以 ontology 为注释来源；后续 CI diff |
| HTTP 破坏性变更 | Phase 5 保留 `evidence` 别名一期 |

---

## 相关文档

- [skills-analysis-tiers.md](./skills-analysis-tiers.md)
- [agentic-analysis-roadmap.md](./agentic-analysis-roadmap.md)
- `data/meta/analysis_ontology.yaml`
- `data/meta/visual_link_contract.yaml`
- `skills/README.md`

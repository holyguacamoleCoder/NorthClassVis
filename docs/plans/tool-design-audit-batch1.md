# 工具设计审计 — 第一批（数据链 + load_skill）

> 对照 Agent 工具设计 14 项清单中的子集逐项检查。  
> 代码基准：`backend/agent/tools/definitions/manifest.py`（约 2026-05-22）。  
> 图例：✅ 基本满足 · ⚠️ 部分满足 · ❌ 明显不足 · N/A 不适用

---

## 1. `inspect_schema`

| 清单项 | 结论 | 现状 | 建议记录 |
|--------|------|------|----------|
| **2 适用场景** | ⚠️ | 描述：查看逻辑资源的列名、类型、样例行、估计行数；末尾「Use before query_data」。未写「首次认识 resource」「确认 class/classes 必填」等具体触发条件。 | 补 **Use when**：首次分析某 `resource`、不确定列名/关联键、确认 `submit_record` 要 `class` / `submit_record_joined` 要 `classes`。与 system prompt「inspect → query → aggregate」对齐。 |
| **3 不适用场景** | ❌ | 无 **Do NOT use for**。未禁止：统计、计数、分组、重复 inspect、写报告、读 CSV。 | 补 **Do NOT**：统计/聚合（用 `query_data` / `aggregate_data`）；同一任务对同一 resource **勿重复调用**；勿代替 `read_file` 读 catalog 全文（analyze 下可读 meta）。consult 下写明：**仅探结构，要数字请切换 analyze**。 |
| **5 resource enum** | ❌ | `resource` 为自由 `string`，description 仅写「见 resource_registry.yaml」。合法 id：`student_info`, `title_info`, `submit_record`, `submit_record_joined`, `week_aggregation`。 | 在 manifest `parameters.properties.resource` 增加 **enum**（从 `data/meta/resource_registry.yaml` 生成）；description 注明各 resource 必填参数（如 `submit_record`→`class`，`submit_record_joined`→`classes`）。 |
| **10 错误可恢复** | ⚠️ | 缺参：`Error: resource is required`。业务错：`Error: {DataResourceError}` / `InvalidParameterError`（如 `majors` 误用于 `submit_record`）文案尚可，但为纯文本，**无** `next_tool` / `example_args` / `fix` 字段。 | 统一错误 JSON 或固定句式：`Error: … \| Next: query_data with …`；对 `InvalidParameterError` 保留 param 名并给示例参数。 |
| **14 consult 是否还要** | ⚠️ | **consult 仍暴露**（`inspect_schema` + `list_files` + `load_skill`）。prompt 写明 consult **无** `query_data`。`loop.py` 将 `inspect_schema` 列入 `_LOOPING_TOOLS`（易空转）。 | **建议保留**（探查元数据），但描述必须写：**consult 仅看表结构，不能出统计**；教师要均值/计数 → 提示切换 **analyze**。可选：同 resource 每会话只 inspect 一次（产品+实现决策）。 |

**本工具额外说明（未列入本批清单项，建议一并记录）**

| 主题 | 现状 | 建议记录 |
|------|------|----------|
| 返回契约（8/9） | 返回 `{resource, columns, sample_rows, row_count_estimate}`（`data/inspect.py`），**不是** TabularResult（无 `schema/rows/meta.result_ref`）。 | 二选一：描述中明确「inspect 返回列元数据，不是 query 结果」；或改 handler 对齐 TabularResult 子集。 |
| 条件必填（4） | `resource` 在 schema 上 required；`class`/`classes` 在 schema 可选，运行时才报错。 | 用 `oneOf` 按 resource 分支 required，或在 description 用表格列出 resource→必填参数。 |
| 性能（6） | 无 `limit`；inspect 会 load 全表再 head 样例。 | 大表资源在描述中警告；或增加 `sample_size` 参数（handler 已有默认 5）。 |

---

## 2. `load_skill`

| 清单项 | 结论 | 现状 | 建议记录 |
|--------|------|------|----------|
| **2 适用场景** | ⚠️ | 「Load full instructions」「Use before generating reports, analyzing CSV…」范围过宽，模型易「先 load 再犹豫」。 | 收窄：**仅当任务需要 SKILL.md 中的固定流程**（如报告模板、特定 SOP）。**学业表结构 → inspect_schema；统计 → query_data**。 |
| **3 不适用场景** | ❌ | 无 Do NOT。 | 补：**勿用 load_skill 代替 inspect/query**；**同一 skill 已成功加载后勿再调**（与 handler 行为一致）；system prompt 已有 skill 摘要时不必重复 load。 |
| **7 缺参：追问 vs 硬编** | ⚠️ | 缺 `name` → `Error: skill name is required`（硬错误，合理）。已加载 → 返回「already loaded…Use query_data…」（**未写入 manifest 描述**）。**`_LOADED_SKILLS` 为模块级全局 set**，非 `LoopState`，多 session/长进程可能串。 | 描述写上「重复 load 将返回提示」；实现将 loaded set 迁入 session；`name` 缺失时 Error 可附带「可用技能见 system prompt 技能列表」。 |
| **14 与 skill 列表联动** | ⚠️ | `name` description：「from available skills list in system prompt」。`system_prompt` 有 `SECTION_SKILLS` + `describe_available()`。**schema 无 enum**，可编造 skill 名。 | 构建 manifest 时把 skill 目录名注入 **`name.enum`**；或 description 动态拼接当前 catalog。与 `skills/registry.py` 单一来源联动。 |
| **14 暴露面** | ⚠️ | consult / analyze / produce **均暴露**。`loop.py` 空转 guard 包含 `load_skill`。 | analyze 可考虑默认不暴露，仅「写报告/用户点名流程」时启用；或强化 prompt：有 `data-csv-analysis` 摘要时先 query 再按需 load。 |

**本工具额外说明**

| 主题 | 现状 | 建议记录 |
|------|------|----------|
| 工具名（1） | ✅ `load_skill` 可读。 | — |
| 返回 8/9 | 返回 SKILL 全文纯文本；无 `{status, skill_name, loaded}`。 | 可选：成功时首行 `[Skill loaded: name]` + 正文，便于 micro_compact 保留状态。 |
| 错误 10 | Unknown skill 等来自 registry，一般无 next step。 | `Error: Unknown skill 'x'. Available: …`（列出 describe_available 摘要）。 |

---

## 3. `query_data`

| 清单项 | 结论 | 现状 | 建议记录 |
|--------|------|------|----------|
| **2 适用场景** | ✅ | 主分析工具：filter/project/group/sort/limit；示例 `submit_record_joined` + `classes`；强调勿用 read_file 读 CSV；说明 TabularResult + `meta.result_ref`。 | 可再加一句：**班级对比、学生筛选、排序预览、导出前抽样**。 |
| **3 不适用场景** | ⚠️ | 相对 read_file 隐含「勿读 CSV」；**未写**：勿用 query 做「只看列结构」（应用 inspect）；勿对 `submit_record_joined` 无 `classes`；consult 模式不可用（靠 mode，描述可再写）。 | 补 Do NOT：列结构探查 → `inspect_schema`；**consult 模式无此工具**；勿重复相同参数 query；专业过滤勿用 `submit_record`（用 joined + `majors`）。 |
| **4 必填明确** | ⚠️ | schema 仅 **required: `resource`**。`where` 为自由 object，description 一行 DSL 说明。`class`/`classes` 对 submit 系资源实际必填但 schema 未标。`filter` 为 deprecated 别名（repair 会转 `where`）。 | `where` 增加 **JSON Schema**（eq/and 等）；按 resource 文档化必填 resolve 参数；**从 schema 移除 `filter`**，仅保留 repair 别名或文档提及。 |
| **5 resource enum** | ❌ | `resource` 自由 string，无 enum。 | 与 `inspect_schema` **共用** registry 生成的 enum；description 链接各 resource 必填参数。 |
| **6 时间/数量/上限** | ⚠️ | `limit` 为 integer，**无 maximum**。运行时：`limit<0` 报错；registry `max_rows=5000`；预览 `PREVIEW_ROW_LIMIT=50`（**未写在 schema**）。 | `limit` 加 `minimum: 0, maximum: 5000`；description 说明「返回 rows 为预览（约 50 行），全量见 `meta.result_ref`」。 |
| **8 结构化状态** | ✅ | TabularResult：`schema` + `rows` + `meta`（`resource`, `truncated`, `result_ref`, `rows_scanned` 等）。 | 保持；可选在 meta 增加 `status: ok`。 |
| **9 证据字段** | ✅ | `rows` 预览 + `meta.result_ref` + `rows_scanned`；`meta.next_step` 指向 `aggregate_data` 示例（`_enrich_query_payload`）。 | 保持；postprocess 已加 `[Summary]` 行，与 9 一致。 |

**本工具额外说明**

| 主题 | 现状 | 建议记录 |
|------|------|----------|
| 错误 10 | 多数 `Error: {exc}`；`InvalidParameterError` 常含 param 与中文说明（优于 inspect）。 | 与 inspect 统一 recovery 格式；对「列不存在」类错误给出 `select`/`inspect_schema` 建议。 |
| 缺参 7 | 无 resource → 明确 Error；resolve 缺 class/classes → 运行时 Error（非 repair 预判）。 | 可选：manifest 按 resource 标 required 字段，repair 提前报 missing。 |

---

## 4. `aggregate_data`

| 清单项 | 结论 | 现状 | 建议记录 |
|--------|------|------|----------|
| **2 适用场景** | ⚠️ | 「对 prior result_ref 或 inline rows 做 aggregate」「Returns TabularResult」。未写典型场景（计数、均值、按班分组）。 | 补：**在 query_data 之后**做 count/mean/min/max、按 `dimensions` 分组；示例 metrics 一行。 |
| **3 不适用场景** | ❌ | 无 Do NOT。 | 补：**不能代替 query**；不能直接对原始 CSV；**不能只传 resource 而不先 query**（若保留 auto-query 须在描述中说明）。 |
| **4 必填明确** | ⚠️ | required：`input`, `metrics`。`metrics[].op` 有 enum；`input` 仅为 object 描述；`metrics[].field` 何时必填未写清。 | `input` 用 `oneOf`：`{result_ref: string}` 或 inline schema+rows；`metrics` items 标 `required: [op]`，description 说明 count 可不填 field、mean 须 field。 |
| **7 是否过度 auto-input** | ⚠️ | **三层自动补 input**：① `runtime/data_chain`：本批最近 query 或 `analysis_context.last_result_ref`，设 `_auto_input`；② handler：`_last_result_ref` → input；③ handler：无 input 但有 `resource+metrics` 时 **内部再跑 query**（`_composite_query_for_aggregate`）。成功时 `meta.auto_input=true`。 | **文档**：manifest 写明系统可能自动注入 `result_ref`。**决策**：建议保留 ①②，减少模型空转；③ 是否保留需产品确认（隐藏 query，模型学不会先 query）。若保留 ③，描述必须写清触发条件。 |
| **8 结构化状态** | ✅ | TabularResult；`meta.auto_input` 标记自动注入。 | 保持；可选 `meta.source_result_ref` 明示上游 query。 |
| **10 错误可恢复** | ✅ | `_aggregate_input_required_message`：要先 query、示例 JSON、可带 `last_result_ref`。与 `loop` aggregate input error guard 配套。 | 保持；可同样改为结构化 error；`metrics` 缺 field 时给示例 metrics。 |

**本工具额外说明**

| 主题 | 现状 | 建议记录 |
|------|------|----------|
| 工具名（1） | ✅ 清晰。 | — |
| resource enum（5） | 可选 `resource` 无 enum。 | 若保留 ③ 路径，resource 应用 enum。 |
| consult 14 | consult **不暴露** aggregate（✅）。 | — |

---

## 第一批优化 Backlog（按优先级）

| 优先级 | 动作 | 涉及工具 |
|--------|------|----------|
| P0 | manifest 描述补全 **Use when / Do NOT** | 全部 4 个 |
| P0 | `resource` **enum**（yaml 生成） | inspect + query（+ aggregate 若保留 resource 参数） |
| P1 | `query_data`：`where` 子 schema、`limit` maximum、移除 schema 中 `filter` | query |
| P1 | `load_skill`：收窄描述 + `name` enum + 与 handler「已加载」对齐 | load_skill |
| P2 | 错误信息统一 recovery 句式或 JSON | inspect、query |
| P2 | `inspect` 返回契约说明或对齐 TabularResult | inspect |
| P2 | `aggregate` auto-input 策略文档化 + 是否保留 `_composite_query_for_aggregate` | aggregate |
| P3 | `_LOADED_SKILLS` 迁入 session | load_skill |
| P3 | consult + inspect 防重复策略（描述或实现） | inspect |

---

## 可复制简表（仅勾选项 + 结论）

```markdown
### inspect_schema
| 项 | 结论 | 现状摘要 | 建议摘要 |
| 2 | ⚠️ | 有 before query，缺具体 when | 补 Use when 三条 |
| 3 | ❌ | 无 NOT for | 补统计/重复/consult 边界 |
| 5 | ❌ | resource 自由 string | yaml → enum |
| 10 | ⚠️ | 纯 Error 文本 | + Next / example |
| 14 | ⚠️ | consult 仍暴露，易空转 | 保留+写清切 analyze |

### load_skill
| 项 | 结论 | 现状摘要 | 建议摘要 |
| 2 | ⚠️ | before reports/CSV 过宽 | 收窄到 SOP/报告 |
| 3 | ❌ | 无 NOT for | 勿替代 inspect/query |
| 7 | ⚠️ | 全局 _LOADED_SKILLS | 迁入 session + 写进描述 |
| 14 | ⚠️ | name 无 enum | enum=catalog |

### query_data
| 项 | 结论 | 现状摘要 | 建议摘要 |
| 2 | ✅ | 主分析工具描述较好 | 微调即可 |
| 3 | ⚠️ | 缺 NOT for inspect/重复 | 补 3 条 NOT |
| 4 | ⚠️ | where 无 schema；class 非 required | where schema + 条件必填 |
| 5 | ❌ | resource 无 enum | 同 inspect |
| 6 | ⚠️ | limit 无 max | max 5000 + 说明预览 50 |
| 8 | ✅ | TabularResult | — |
| 9 | ✅ | rows + result_ref + next_step | — |

### aggregate_data
| 项 | 结论 | 现状摘要 | 建议摘要 |
| 2 | ⚠️ | 缺典型 when | 补 query 之后聚合 |
| 3 | ❌ | 无 NOT for | 勿代替 query |
| 4 | ⚠️ | input/metrics 结构弱 | oneOf input |
| 7 | ⚠️ | 三层 auto-input | 文档化+决策是否保留③ |
| 8 | ✅ | TabularResult + auto_input | — |
| 10 | ✅ | 缺 input 提示最好 | 保持并统一格式 |
```

---

## 变更记录

| 日期 | 说明 |
|------|------|
| 2026-05-22 | 初版：第一批 4 工具审计（含现状与建议记录） |

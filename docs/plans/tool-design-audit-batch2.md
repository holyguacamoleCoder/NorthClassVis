# 工具设计审计 — 第二批（文件与目录）

> **优先级 B**：常「抢」数据链的活（模型用读目录/读文件代替 `inspect_schema` / `query_data`）。  
> 对照 Agent 工具设计 14 项清单中的相关子集；与 [`tool-design-audit-batch1.md`](tool-design-audit-batch1.md) 同格式。  
> 代码基准：`manifest.py`、`handlers/base_tool.py`、`permission/`（约 2026-05-22）。  
> 图例：✅ 基本满足 · ⚠️ 部分满足 · ❌ 明显不足 · N/A 不适用

---

## 跨工具：与数据链的关系

| 主题 | 现状 | 建议记录 |
|------|------|----------|
| **模式裁剪** | **consult**：`list_files` + `inspect_schema` + `load_skill`，**无** `read_file`（`modes.py` 注释写明避免与「勿读 CSV」冲突）。**analyze/produce**：含 `read_file` + `list_files` + 数据链工具。**produce** 才含 `write_file` / `edit_file`。 | 在 `list_files` / `read_file` 描述中重复一句：**学业 CSV → inspect/query，勿用本批工具**。system prompt 已有，manifest 应对齐。 |
| **权限 vs 描述** | 原始 CSV：`permission.manager` + `is_raw_dataset_path` 拒绝 `read_file`（中英文 reason 指向 inspect/query）。写路径：仅 `reports/**`、`exports/**`（`rules.py` + `is_writable_path`）；handler `_safe_path` 限制在 `data/` 内。 | 描述写 **policy 摘要**（可读/可写目录），并注明「越权路径由 permission 拒绝，非工具 Error」。 |
| **与 batch1 联动** | `query_data` 描述已写 Prefer over read_file on Data_*.csv。 | P0：强化 `list_files` 的 Do NOT，减少 consult 下「列目录 → 以为能分析」的空转。 |

---

## 1. `read_file`

| 清单项 | 结论 | 现状 | 建议记录 |
|--------|------|------|----------|
| **1 工具名** | ✅ | `read_file` 语义清晰；repair 对 read/write 模糊匹配有互斥保护（`repair.py`）。 | — |
| **2 适用场景** | ✅ | manifest：**「Read text under meta/, reports/, or exports/ (analyze/produce only)」**；system prompt 与 `meta/data_catalog.md` 摘要一致。 | 可补 **Use when**：读已有报告草稿、catalog 全文、exports 小文本；确认报告里引用的文件路径。 |
| **3 不适用场景** | ✅ | manifest：**「Never use for Data_*.csv or Data_SubmitRecord/; use inspect_schema/query_data instead」**；`prompts.py` 禁止读三类原始 CSV；permission 对 raw dataset **deny** 并给切换 analyze 文案。 | 补 **Do NOT**：`list_files` 后勿对 `Data_*` 再 read；二进制/超大文件；**consult 模式不可用**（靠 mode，建议写入描述）。 |
| **4 必填明确** | ✅ | schema：`required: ["path"]`；`limit` 可选。 | `path` description 举例：`meta/data_catalog.md`、`reports/academic_analysis_Class1.md`。 |
| **5 路径约束（schema）** | ⚠️ | `path` 为自由 string；**无 enum / pattern**。实际约束：handler `_safe_path`（仅 `data/`、禁 `.agent`/隐藏段）、permission（raw CSV、governance）。 | description 列 **允许前缀**：`meta/`、`reports/`、`exports/`；**禁止模式**与 permission 一致（可引用「见 permission paths」）。不必 enum 全路径。 |
| **6 数量/上限** | ⚠️ | `limit` 为 integer，**无 minimum/maximum**；handler：`limit` 截断**行数**，再整体 `[:MAX_OUTPUT_LENGTH]`（50000 字符）。未说明默认「读全文直到 50k」。 | `limit` 加 `minimum: 1, maximum: 5000`（或与 `MAX_OUTPUT_LENGTH` 联动说明）；描述写：**省略 limit 时可能截断至 50k 字符**。 |
| **8 结构化状态** | ❌ | 成功返回**纯文本**（文件内容或截断提示行）；无 `{status, path, lines_read, truncated}`。 | 轻量不改 handler：首行 `[Read OK: path, lines=N, truncated=bool]`；或 JSON 包装（与 TabularResult 区分，避免模型混用）。 |
| **9 证据字段** | ❌ | 无 `bytes_read` / `sha` / `mtime`；大结果靠 `maybe_persist_output`（postprocess）外置，**未在返回中提示 ref**。 | 截断时在文末固定：`[Truncated: use smaller limit or query_data for tables]`；若 persist，追加 `[Full output: …]`（若 compact 层已有则写进描述）。 |
| **10 错误可恢复** | ⚠️ | `File not found`、`UTF-8`、`WORKSPACE_PATH_ERROR`、`HIDDEN_PATH_ERROR` 为 `Error: …` 纯文本。permission deny 的 raw CSV reason **较好**（含 inspect/query/analyze 切换）。 | 统一 `Error: … \| Next: list_files path=…` 或 `inspect_schema`；not found 时 suggest 常见路径。 |
| **14 模式暴露** | ✅ | **consult 不暴露** `read_file`（有测试 `test_consult_has_no_read_file_tool`）。analyze/produce 暴露。 | 保持；描述中写 **analyze/produce only**。 |

**本工具额外说明**

| 主题 | 现状 | 建议记录 |
|------|------|----------|
| 抢数据链 | 描述与 permission 已拦 CSV；模型仍可能 read `reports/` 里大 JSON 或重复读 catalog。 | 与 batch1 P0 一致：prompt 强调「数字用 query，read 只读人写文档」。 |
| postprocess | `PATH_TOOLS` 会 `track_recent_file` 供 compact。 | — |

---

## 2. `list_files`

| 清单项 | 结论 | 现状 | 建议记录 |
|--------|------|------|----------|
| **1 工具名** | ⚠️ | `list_files` 可理解，但与「列目录」相比略泛（未体现 workspace 根）。 | 可保持名称；description 首句点明 **data workspace 根目录**。 |
| **2 适用场景** | ❌ | 仅一句：**「List files/directories under data workspace.」** 无 when：找报告、找 export、确认 Class1 CSV 文件名等。 | 补 **Use when**：不确定 `reports/`/`exports/` 下有何文件；consult 下探索目录结构（**不读内容**）。 |
| **3 不适用场景** | ❌ | 无 Do NOT；未写「勿用来认 CSV 列结构」「勿代替 query」。 | 补 **Do NOT**：**勿用于查看 Data_*.csv 列名/样例**（用 `inspect_schema`）；**勿用于统计行数**（用 `query_data`）；勿期望列出逻辑 resource（用 registry + inspect）。 |
| **4 必填明确** | ⚠️ | schema **无 required**；`path`/`recursive`/`limit` 均可省略。 | 在 description 说明默认行为；或 `required: []` 显式 + 文档化默认（见 7）。 |
| **5 路径约束** | ⚠️ | `path` 自由 string；handler 同样 `_safe_path`。permission：`list_files` + `*` allow。 | `path` description：相对 `data/`，常用 `.`、`reports`、`exports`、`Data_SubmitRecord`（仅列名，不读内容）。 |
| **6 数量/上限** | ⚠️ | `limit` 无 schema 上限；handler 默认 **200**（manifest `defaults`）；`limit>0` 时截断并 append `... (N more entries)`。recursive 无深度限制。 | `limit` 加 `maximum: 500`；描述默认 200；recursive 时警告「大目录用 path 缩小范围」。 |
| **7 缺参 / 默认值** | ⚠️ | `defaults={"path": ".", "recursive": False, "limit": 200}` 经 dispatcher 注入；**OpenAI schema 未展示默认值**；repair `apply_arg_repairs` 对空 `{}` 补默认（测试 `test_apply_list_files_defaults`）。模型常省略 path/limit，**靠隐藏默认**。 | description 写明：**省略 path → 列出 data/ 根；limit 默认 200**。可选在 schema 用 `default` 字段（若 API 支持）或 examples。 |
| **8 结构化状态** | ❌ | 返回换行分隔路径列表或 `(empty directory)`；无 `{entries[], truncated, root}`。 | 可选 JSON：`{root, entries, truncated, count}`；或保留文本但在首行 `[List: root=., count=N, truncated=bool]`。 |
| **9 证据字段** | ❌ | 无文件类型、大小、mtime；目录项无 `/` 后缀规则在文本里（目录带 `/`）。 | 低优先级；若加 meta 行即可。 |
| **10 错误可恢复** | ⚠️ | `Path not found`、`Not a directory`、workspace/hidden 与 read 相同。 | not found 时 suggest `path="."` 或 `reports`；与 read_file 对齐 Error 句式。 |
| **14 模式暴露** | ⚠️ | **consult / analyze / produce 均暴露**（三模式都有 `list_files`）。consult 无 read/query，易 **list → 空转**（只列 `Data_SubmitRecord/` 文件名却无法分析）。 | 保留 consult 暴露；**必须**补 Do NOT + prompt：**列目录 ≠ 能读 CSV 内容**；要分析请切 analyze。可选 loop guard：consult 连续 list 同 path。 |

**本工具额外说明**

| 主题 | 现状 | 建议记录 |
|------|------|----------|
| 抢数据链 | consult 唯一「看磁盘」手段，模型常 list `Data_SubmitRecord` 再卡住（无 read_file/query）。 | 与 inspect_schema 描述联动：**看到 CSV 文件名后 → 切 analyze → inspect_schema(resource=submit_record)**。 |
| repair | `file_path`→`path` 等全局别名可用。 | — |

---

## 3. `write_file`

| 清单项 | 结论 | 现状 | 建议记录 |
|--------|------|------|----------|
| **1 工具名** | ✅ | `write_file` 清晰。 | — |
| **2 适用场景** | ❌ | **「Write to a file in the current workspace.」** 过泛；未写 deliverable、报告落盘、exports。 | 补 **Use when**：在 **produce** 下新建/覆盖 `reports/*.md`、`exports/*`；用户明确要求保存分析结论。 |
| **3 不适用场景** | ❌ | 无 Do NOT。 | 补：**勿写** `Data_*.csv`、原始数据集、`.agent`；**analyze/consult 不可用**；**勿代替 query 导出表**（若需结构化结果用 query + 再写摘要）。 |
| **4 必填明确** | ✅ | `required: ["path", "content"]`。 | `content` description 注明 UTF-8、换行规范化（handler `newline="\n"`）。 |
| **5 路径约束（schema）** | ❌ | `path` 无 pattern；**可写范围未出现在 schema**。实现：`WRITE_ALLOW_PATTERNS` = `reports/**`、`exports/**`；deny `Data_*.csv`；`_safe_path` + `is_writable_path` fallback deny。 | description：**仅 `reports/`、`exports/` 下**（任意深度）；示例 path。schema 可选 `pattern` 或 `description` 枚举前缀。 |
| **6 大小/安全** | ⚠️ | 无 `content` 长度上限；`CONCURRENCY_UNSAFE_TOOL` 串行。bash 写文件被拦，引导用本工具。 | 可选 `content` maxLength 或 handler 警告超大写入；描述「报告建议 markdown」。 |
| **8 结构化状态** | ⚠️ | 成功：`Wrote {n} bytes to {path}` 单行文本。 | 可加 `status=ok` 或 JSON；与 edit 统一格式。 |
| **9 证据字段** | ⚠️ | 返回写入字节数与 path，无 checksum/是否覆盖。 | 可选 `created` vs `overwritten`（handler 可查 `exists()`）。 |
| **10 错误可恢复** | ⚠️ | permission deny 文案含 `writable_path_denial_reason`；handler 路径逃逸同 read。 | Error 附 **Next: use path under reports/…**；analyze 模式 deny 时写 **switch to produce**。 |
| **11 二次确认** | ⚠️ | **不在工具描述**；produce 下未命中 allow 规则时可能 `behavior: ask` + `permission.ask_user`（CLI approval）。命中 `reports/**` allow 则直接写。 | description 写：**produce 下写入 reports/exports 通常直接执行；其它路径需用户批准**（与实现一致）。产品若要求覆盖前确认，需 approval 规则或 hook，非仅改 manifest。 |
| **14 模式暴露** | ✅ | 仅 **produce**（`WRITE_TOOLS`；analyze/consult `_mode_check` deny write）。 | 保持；描述首句 **produce mode only**。 |

---

## 4. `edit_file`

| 清单项 | 结论 | 现状 | 建议记录 |
|--------|------|------|----------|
| **1 工具名** | ✅ | `edit_file` 清晰；与 `write_file` 配对。 | — |
| **2 适用场景** | ❌ | **「Edit a file in the current workspace.」** 同 write 过泛。 | 补 **Use when**：小范围修订已有 `reports/` 草稿（替换一段章节）；`old_text` 必须唯一匹配。 |
| **3 不适用场景** | ❌ | 无 Do NOT。 | 同 write_file；另加：**勿用于大段重写**（用 write_file 整文件）；**old_text 未命中勿盲试**（先 read_file 核对）。 |
| **4 必填明确** | ✅ | `required: ["path", "old_text", "new_text"]`。 | 描述 **old_text 须与文件 UTF-8 内容完全一致**（含换行）；仅替换**首次**出现（handler `replace(..., 1)`）。 |
| **5 路径约束** | ❌ | 与 write 相同，靠 permission + handler，schema 无说明。 | 与 write_file **共用** path 策略描述（可抽 manifest 常量 `_WRITABLE_PATH_DOC`）。 |
| **6–10** | ⚠️ | 与 write 类似；特有错误 **`Text not found in {path}`** 无 next step。 | `Text not found` → suggest `read_file` 取片段再 edit；或缩小 old_text。 |
| **11 二次确认** | ⚠️ | 同 write（permission ask，不在 manifest）。 | 同 write_file。 |
| **14 模式暴露** | ✅ | 仅 produce。 | 保持。 |

**write / edit 合并说明**

| 主题 | 现状 | 建议记录 |
|------|------|----------|
| 与 read 对称 | read 描述最完整；write/edit 最弱。 | 一次性补全 write/edit 的 Use/Do NOT/路径/模式，与 read 的 CSV 禁令对称。 |
| 测试 | `test_permission.py` 覆盖 consult 无 read、raw CSV deny、governance path。 | 为 list_files 描述变更可加「文档性」测试或仅 manifest 快照测试。 |

---

## 第二批优化 Backlog（按优先级）

| 优先级 | 动作 | 涉及工具 |
|--------|------|----------|
| P0 | **list_files** 补全 Use when / Do NOT（CSV 结构 → inspect；统计 → query；consult 边界） | list_files |
| P0 | **write_file / edit_file** 描述：produce only + 可写 `reports/`、`exports/` + Do NOT 原始数据 | write, edit |
| P1 | **read_file** `limit` schema maximum + 描述 50k 截断 | read_file |
| P1 | **list_files** 描述化 defaults（path=. limit=200）；`limit` maximum | list_files |
| P1 | 四工具 `path` property **description**（允许/禁止前缀，与 `permission/paths.py` 一致） | 全部 |
| P2 | 返回首行 status / truncated 提示（read/list） | read, list |
| P2 | **edit** `Text not found` recovery 句式 | edit_file |
| P2 | write/edit 描述中写明 **permission ask** 何时触发 | write, edit |
| P3 | list_files 结构化返回或 consult 防重复 list guard | list_files, loop |

---

## 可复制简表

```markdown
### read_file
| 项 | 结论 | 现状摘要 | 建议摘要 |
| 1 | ✅ | 名清晰 | — |
| 2 | ✅ | meta/reports/exports + analyze/produce | 补 Use when 举例 |
| 3 | ✅ | 勿读 Data_* + permission deny | 补 consult 不可用 |
| 5 | ⚠️ | path 无 pattern | description 列允许前缀 |
| 6 | ⚠️ | limit 无 max；50k 字符 cap | limit max + 说明 |
| 8/9 | ❌ | 纯文本 | 首行 status 或轻量 JSON |
| 14 | ✅ | consult 不暴露 | 描述写明 |

### list_files
| 项 | 结论 | 现状摘要 | 建议摘要 |
| 1 | ⚠️ | 名尚可 | description 点明 data/ |
| 2 | ❌ | 一句过短 | 补 Use when |
| 3 | ❌ | 无 NOT for CSV/inspect | 补三条 Do NOT |
| 6/7 | ⚠️ | limit 无 max；默认靠 defaults/repair | 写入描述 + limit max |
| 14 | ⚠️ | consult 仍暴露 | Do NOT + 切 analyze |

### write_file / edit_file
| 项 | 结论 | 现状摘要 | 建议摘要 |
| 1 | ✅ | 名清晰 | — |
| 2/3 | ❌ | 描述过泛；无 Do NOT | produce + reports/exports + 禁 Data_* |
| 5 | ❌ | 路径靠 permission | schema/description 写可写范围 |
| 11 | ⚠️ | 确认在 permission ask | 描述说明；非工具参数 |
| 14 | ✅ | 仅 produce | 描述首句标明 |
```

---

## 变更记录

| 日期 | 说明 |
|------|------|
| 2026-05-22 | 初版：第二批 4 工具（read/list/write/edit）含现状与建议记录 |
| 2026-05-22 | 实现 P0–P3：manifest 描述/schema、base_tool 状态行与错误恢复、consult list_files 循环 guard、test_file_tools_batch2 |

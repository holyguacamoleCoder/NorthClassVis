# 工具设计审计 — 第三批（会话与上下文）

> **优先级 C**：不直接读表，但影响多步分析、上下文预算与跨会话行为；模型可能**过度** `todo_write` / `compact`，或**误用** `save_memory` 存本应 query 的事实。  
> 对照 Agent 工具设计 14 项清单中的相关子集；与 [batch1](tool-design-audit-batch1.md)、[batch2](tool-design-audit-batch2.md) 同格式。  
> 代码基准：`manifest.py`、`handlers/todo_write.py`、`handlers/compact.py`、`handlers/save_memory.py`、`loop.py`、`context/*`、`common/memory.py`（约 2026-05-22）。  
> 图例：✅ 基本满足 · ⚠️ 部分满足 · ❌ 明显不足 · N/A 不适用

---

## 范围说明

| 工具 | 在 MANIFEST | 本批审计 |
|------|-------------|----------|
| `todo_write` | ✅ | ✅ |
| `compact` | ✅ | ✅ |
| `save_memory` | ✅ | ✅ |
| `bash` | ❌（仅 `handlers/base_tool.run_bash`，未注册 LLM tool） | 脚注：不暴露 |

---

## 跨工具：模式、持久化与 loop 协作

| 主题 | 现状 | 建议记录 |
|------|------|----------|
| **模式裁剪** | `SESSION_TOOLS = {todo_write, compact, save_memory}`。**consult 不暴露**（`filter_tools` 测试仅含 inspect/list/load_skill）。**analyze / produce** 均暴露三者；produce 另含 write/edit。 | manifest 各工具描述写明 **analyze+produce**；consult 下「无 todo/compact/save_memory」与 mode hint 一致。 |
| **与数据链** | 不读写 CSV；但 `todo_write` 可能占多轮而无 `query_data`；`compact` 后模型可能丢失 query 结果细节（micro_compact 会保留 TabularResult 摘要行）。 | `compact` Do NOT：**压缩前确认关键 result_ref 已用于 aggregate 或已写入报告**；`save_memory` Do NOT：存表结构/统计结果（应用 query + 报告文件）。 |
| **全局单例** | `TodoManager`（`todo_manager`）与 batch1 的 `_LOADED_SKILLS` 类似：进程级；`SessionManager._activate` 时 `reset_todo_state` + `apply_todo_snapshot` 从 `todo.json` 恢复。 | 文档化「换 session 会恢复 todo」；长期考虑 todo 状态仅绑 `LoopState`/session，避免测试串扰。 |
| **权限** | `rules.py` 对 `todo_write`、`compact` 为 `allow` + `path: *`（path 无意义）。`save_memory` **无** 单独 rule，走 `MODE_TOOL_ALLOWLIST` 直接 allow。均无 ask。 | `save_memory` 可选增加 deny/ask（覆盖敏感路径类 memory）；低优先级。 |

---

## 1. `todo_write`

| 清单项 | 结论 | 现状 | 建议记录 |
|--------|------|------|----------|
| **1 工具名** | ✅ | `todo_write` 语义明确（写会话计划，非磁盘 todo 文件）。 | — |
| **2 适用场景** | ⚠️ | manifest 仅一句：**「Rewrite the current session plan for multi-step work.」** `prompts.py` 有「跨表、多班级、写报告」analyze 场景。 | 补 **Use when**：≥3 步且步骤会跨多轮工具（inspect→query→aggregate→写报告）；任务开始时建计划；**每完成一步后更新** status。 |
| **3 不适用场景** | ❌ | 无 Do NOT。 | 补：**单轮问答、单次 query 即可回答** 不必 todo；**勿用 todo 代替 query/aggregate**；**勿超过 12 项**（handler `MAX_ITEMS=12`）；consult 不可用。 |
| **4 必填明确** | ✅ | `required: ["items"]`；每项 `required: ["content", "status"]`；`status` **enum** `pending\|in_progress\|completed`；`active_form` 可选。 | description 说明：**至多 1 个 `in_progress`**（handler 强制）；`active_form` 仅在 in_progress 时显示。 |
| **6 数量上限** | ⚠️ | schema 无 `maxItems`；运行时 `len(items) > 12` → `ValueError`。 | `items` 加 `maxItems: 12`；建议描述「推荐 ≤5 步」。 |
| **7 缺参 / 默认** | ⚠️ | 空 `items` 会清空计划并返回 `No session plan yet.`；无默认模板。 | 可选：空 items 时 Error「items required」或保留清空但描述写清。 |
| **8 结构化状态** | ⚠️ | 返回**可读文本**（`[ ]` / `[>]` / `[√]` + `Completed: n/m`），非 JSON。计划状态在 `TodoManager.state`，会话 `todo.json` 持久化。 | 可选返回 JSON `{items, completed, total}` + 同文本；或首行 `[Plan updated: 2/5 completed]`。 |
| **9 证据字段** | N/A | 计划本身非分析证据。 | — |
| **10 错误可恢复** | ⚠️ | 校验失败抛 `ValueError`（无 content、非法 status、多个 in_progress、>12 项）→ executor 侧应为 `Error: …` 文本。 | 统一句式并举例合法 item：`{"content":"…","status":"in_progress","active_form":"…"}`。 |
| **12 与 loop 联动** | ✅ | `loop.py`：本轮无 `todo_write` 则 `mark_round_without_todo_update()`；`round_since_update >= 3` 时 `get_todo_reminder()` 追加到 todo 工具结果（`<reminder>Refresh the session plan…`）。**未**列入 `_LOOPING_TOOLS`。 | 保持；manifest 写：**若 3 轮未更新计划，系统会提醒**。 |
| **14 模式暴露** | ✅ | analyze / produce；consult 无。 | 描述标明 analyze+produce。 |

**本工具额外说明**

| 主题 | 现状 | 建议记录 |
|------|------|----------|
| 抢分析时间 | 模型可能对简单任务也先 todo 再 query，或多轮只改 todo 不 query。 | prompt：**有明确一步查询即可时直接 query**；P2：loop 统计「连续 N 轮仅 todo_write」软提醒（可选）。 |
| 与 batch1 | 多步分析路径与 `query_data`/`aggregate_data` 配套。 | todo 步骤文案应引用 resource/query，避免「读 CSV」类表述。 |

---

## 2. `compact`

| 清单项 | 结论 | 现状 | 建议记录 |
|--------|------|------|----------|
| **1 工具名** | ✅ | `compact` 简短；与「macro compact / micro compact」概念一致。 | — |
| **2 适用场景** | ⚠️ | manifest：**长线程或需要 refocus 时**；`prompts.py`：对话过长时用 compact 或依赖自动压缩。 | 补 **Use when**：上下文接近上限、重复失败、用户要求「总结后继续」；可选 `focus` 保留当前目标（schema 已有 description）。 |
| **3 不适用场景** | ❌ | 无 Do NOT。 | 补：**勿在刚拿到关键 query/aggregate 结果后立即 compact**（除非仍超长）；**系统每轮可能已 micro/macro 自动压缩** — 勿每轮都手动 compact；**不能代替** `query_data` 减数据量。 |
| **4 必填明确** | ✅ | 无 required；`focus` 可选 string。 | — |
| **6 预算相关** | ⚠️ | 实际压缩由 `loop._apply_manual_compaction` → `compact_history`（LLM 摘要，`context_limit` 默认 50k 等）；handler **仅占位**。schema **未说明**与自动压缩关系。 | 描述写：**手动触发 macro 压缩**；每轮开始前 loop 可能已 `micro_compact_messages`。 |
| **7 实现分裂** | ⚠️ | `run_compact` 返回 `"Compacting conversation (focus: …)…"`；**真实改写 messages** 在 tool batch 结束后 `loop.py`（`compact_calls` + `compact_config.enabled`）。模型看到的 tool 结果与最终上下文不一致。 | 工具结果改为 `[Compact applied]` 或 loop 用 tool 结果承载摘要首段；描述写明「副作用在 loop，非本返回值」。 |
| **8 结构化状态** | ❌ | 占位字符串；压缩后 messages 变为 user 摘要 + tail（`build_compacted_messages`），`CompactState.has_compacted`、`recent_files` 写入 session `compact.json`。 | 成功返回：`Compacted: N messages → summary + K tail turns`；含 `recent_files` 列表。 |
| **9 证据字段** | N/A | 压缩丢证据风险在 micro（对旧 tool 结果 placeholder，query 类保留 summary 行）。 | `compact` Do NOT 前确认；micro 已对 TabularResult 保留 `result_ref` 摘要（见 `test_micro_compact_preserves_tabular_summary`）。 |
| **10 错误可恢复** | ⚠️ | `compact_config.enabled=False` 时 loop 不执行 manual compact，工具仍返回占位成功。recovery 路径另有 `_apply_recovery_compaction`。 | 禁用时 manifest 或 mode hint 说明；失败时 suggest 缩小任务 / 新会话。 |
| **12 loop / recovery** | ✅ | 每轮 `_apply_pre_turn_compaction`；recovery `COMPACT` 策略也会 `compact_fn`。用户可见错误文案提及 compact。 | 保持；描述区分 **自动 vs 本工具**。 |
| **14 模式暴露** | ✅ | analyze / produce；consult 无。 | — |

**本工具额外说明**

| 主题 | 现状 | 建议记录 |
|------|------|----------|
| focus 参数 | 传入 `build_compacted_messages(..., focus=...)`，影响摘要 prompt。 | 描述给示例 focus：`"Class1 成绩分析，保留 result_ref"`。 |
| 与 read/list | `CompactState.recent_files` 来自 batch2 `PATH_TOOLS` 追踪。 | compact 后模型应知 recent_files 在摘要 user 消息中注入。 |

---

## 3. `save_memory`

| 清单项 | 结论 | 现状 | 建议记录 |
|--------|------|------|----------|
| **1 工具名** | ✅ | `save_memory` 清晰；与磁盘 `.memory/*.md` 一致。 | — |
| **2 适用场景** | ⚠️ | manifest 一句：**跨会话持久记忆**。`prompts.py` **`MEMORY_GUIDANCE`** 较完整（user/feedback/project/reference 四类场景）。 | manifest **引用或缩写 MEMORY_GUIDANCE**；**Use when**：教师明确偏好、纠正方法、项目约定、外部链接。 |
| **3 不适用场景** | ⚠️ | manifest 无 Do NOT；**MEMORY_GUIDANCE** 有「勿存 CSV 结构、单次 TODO、密钥」。 | 将 guidance 中 **不要保存** 三条并入 manifest description；强调 **catalog/字段/统计数字 → inspect/query/report 文件**。 |
| **4 必填明确** | ✅ | `required: ["name", "description", "type", "content"]`；`type` **enum** 四类 + description 释义。 | — |
| **5 命名约束** | ⚠️ | `name` 自由 string；handler 规范为 `[a-z0-9_-]` 文件名，非法则 `Error: invalid memory name`。 | description：**短标识符**，示例 `prefer_tabs`、`report_style_class1`；同名覆盖旧文件（应写明）。 |
| **6 大小/上限** | ⚠️ | `content` 无 maxLength；`MEMORY.md` index `MAX_INDEX_LINES=200`。 | 可选 content 长度上限；描述「一条记忆一事」。 |
| **8 结构化状态** | ⚠️ | 成功返回单行：`Saved memory 'name' [type] to path`；`load_all()` 刷新 prompt 注入。 | 可选 JSON `{status, name, type, path, overwritten}`。 |
| **9 证据字段** | N/A | 记忆是偏好/约定，非单次分析证据。 | 与 analyze 结论区分：结论写报告，记忆写偏好。 |
| **10 错误可恢复** | ⚠️ | `type` 非法 → `Error: type must be one of …`；name 非法 → `Error: invalid memory name`。 | 附合法示例一行 JSON。 |
| **11 二次确认** | ❌ | **无**用户确认；写入即落盘 `.memory/{safe_name}.md`。 | 产品决策：敏感 project 记忆是否 ask；描述写 **覆盖同名记忆**。 |
| **14 模式暴露** | ✅ | analyze / produce（`SESSION_TOOLS`）；consult 无。测试 `test_save_memory_in_analyze_mode`。 | produce 描述可写：交付后保存报告风格偏好。 |

**本工具额外说明**

| 主题 | 现状 | 建议记录 |
|------|------|----------|
| 与 system prompt | 已有记忆会在下轮 `load_memory_prompt()` 注入。 | 保存后无需再次 save 同内容；描述写 **更新用同名 name 覆盖**。 |
| DreamConsolidator | `memory.py` 有跨会话整理占位（7 gates），非 LLM tool。 | 与 save_memory 分工：工具=教师显式记忆，dream=后台整理（未来）。 |

---

## 未注册：`bash`（脚注）

| 主题 | 现状 | 建议记录 |
|------|------|----------|
| 暴露 | `run_bash` 在 `base_tool.py`：cwd=`DATA_DIR`，120s timeout，危险命令与无 UTF-8 写文件拦截。 | **保持不注册**为宜，避免与 read/write/query 抢活；若未来暴露，需单独 batch 审计 permission 与模式。 |

---

## 第三批优化 Backlog（按优先级）

| 优先级 | 动作 | 涉及工具 |
|--------|------|----------|
| P0 | 三者补全 **Use when / Do NOT**（与 `MEMORY_GUIDANCE`、loop 行为对齐） | todo, compact, save_memory |
| P0 | `compact` 描述：**手动 macro vs 自动 micro/macro**；占位返回值与 loop 副作用 | compact |
| P1 | `todo_write`：`items.maxItems=12`、in_progress 规则、consult 不可用 | todo_write |
| P1 | `save_memory`：manifest 并入勿存清单 + 同名覆盖说明 | save_memory |
| P2 | `compact` 成功返回含摘要统计；或 loop 改写 tool result | compact |
| P2 | `todo_write` 错误 recovery 示例；可选 JSON 返回 | todo_write |
| P3 | 连续多轮仅 todo 的 loop 软 guard | todo_write, loop |
| P3 | `save_memory` 覆盖前 ask（产品） | save_memory |

---

## 可复制简表

```markdown
### todo_write
| 项 | 结论 | 现状摘要 | 建议摘要 |
| 1 | ✅ | 名清晰 | — |
| 2 | ⚠️ | 一句 multi-step | 补跨表/多步 when |
| 3 | ❌ | 无 NOT for | 单轮/query 不必；≤12 项 |
| 4 | ✅ | items+status enum | 写清仅 1 个 in_progress |
| 6 | ⚠️ | max 12 仅运行时 | schema maxItems |
| 8 | ⚠️ | 文本 checklist | 可选 JSON |
| 12 | ✅ | 3 轮 reminder | 写入描述 |
| 14 | ✅ | analyze/produce | consult 无 |

### compact
| 项 | 结论 | 现状摘要 | 建议摘要 |
| 1 | ✅ | 名清晰 | — |
| 2 | ⚠️ | 长线程/refocus | 补接近上限 when |
| 3 | ❌ | 无 NOT for | 勿压刚拿到的 query 结果；少用手动 |
| 7 | ⚠️ | handler 占位，loop 真压缩 | 描述+返回值对齐 |
| 8 | ❌ | 占位字符串 | 返回压缩统计 |
| 12 | ✅ | 自动+recovery+手动 | 区分自动/手动 |
| 14 | ✅ | analyze/produce | — |

### save_memory
| 项 | 结论 | 现状摘要 | 建议摘要 |
| 1 | ✅ | 名清晰 | — |
| 2 | ⚠️ | manifest 短；prompt 详 | 并入 MEMORY_GUIDANCE |
| 3 | ⚠️ | 仅 prompt 有勿存 | 写入 manifest |
| 4 | ✅ | 全必填+type enum | — |
| 11 | ❌ | 无确认即写入 | 说明覆盖；可选 ask |
| 14 | ✅ | analyze/produce | — |
```

---

## 变更记录

| 日期 | 说明 |
|------|------|
| 2026-05-22 | 初版：第三批 3 工具（todo_write / compact / save_memory）+ bash 脚注 |
| 2026-05-22 | 实现 P0–P3：manifest、todo/compact handlers、loop compact 结果同步与 todo-only guard、memory 返回格式 |

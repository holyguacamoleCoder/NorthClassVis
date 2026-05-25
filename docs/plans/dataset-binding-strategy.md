# 查询结果绑定策略（内存 + 硬盘，可链式可新建）

> 目标：保留 data 链（query → ref → aggregate），同时避免「第二问误用第一问数据集」；
> **不能写死**「跨 turn 必拒绝」或「永远用 last」——教师常要求 query2 **基于** query1（如「汇总这 10 条」）。

---

## 1. 两层存储（不变）

| 层 | 职责 | 生命周期 |
|----|------|----------|
| **硬盘** | `task_outputs/query-results/*.json` + `sessions/<id>/datasets.jsonl` | 会话内持久；可按 `dataset_id` 显式引用 |
| **内存（工作集）** | 当前 **user_turn** 内的指针与候选列表 | 新用户消息 `begin_user_turn()` 清空；不删硬盘 |

内存不是「全局 last」，而是 **带意图的绑定上下文**。

---

## 2. 核心概念：Dataset 记录 + 绑定意图

每次 `query_data` 登记一条 **DatasetRecord**（已有），扩展元数据：

```yaml
dataset_id: ds_abc
result_ref: query-results/xxx.json
user_turn: 3
result_rows: 10          # 落盘行数
rows_scanned: 22960      # 扫描口径（过滤后、limit 前）
query_limit: 10 | null
has_group_by: false
select: [student_ID, title_ID, score]
classes: [Class1]
resource: submit_record
```

**绑定意图**（BindingIntent）在 aggregate 时决定用哪条记录，来源（优先级从高到低）：

1. **显式**：`input.result_ref` / `input.dataset_id` / `input.chain_from_dataset_id`
2. **工具参数**：`aggregate_data.bind: chain | fresh | auto`（可选，默认 `auto`）
3. **自动推断**（`auto`）：兼容性打分，在 **本会话 catalog + 本 turn 数据集** 中选最佳

---

## 3. 三种教师场景（不能写死一种规则）

### A. 链式续算（query2 基于 query1）

例：「最低 10 条」→「汇总**这些记录**的条数、均值」。

- 应用 **同一** `dataset_id` / ref（limit=10 那次 query）
- 不应再跑全量 query（除非模型要补列）
- 信号：`这些/上述/刚才`、同 turn、aggregate 紧跟 limit query、`bind=chain`

### B. 新口径（query2 与 query1 数据集不同）

例：第一问 10 条切片 → 第二问「全班规模、均分、偏科」。

- **必须** 新 `query_data`（全量 Class1）
- 禁止把 10 行 ref 当全班（`result_rows=10` vs `rows_scanned≈2万`）
- 信号：新 user_turn、指标含「全班」语义、`count_distinct(student_ID)` 且 prior 仅 10 行、`bind=fresh`

### C. 显式回看硬盘（跨 turn 故意用旧结果）

例：「用刚才那份最低分列表再算一遍均分」。

- 允许 **跨 turn** 使用 catalog 中的 `dataset_id`（显式指定）
- **禁止** 静默 `working_active_ref` 跨 turn 自动注入

---

## 4. 绑定解析算法（`auto` 模式）

```
resolve_aggregate_input(intent, catalog, turn_datasets, explicit_input):
  if explicit_input.dataset_id or explicit_input.result_ref:
    rec = resolve(explicit_input)
    if compatibility(rec, intent) < THRESHOLD:
      return Error + suggest_fresh_query_or_other_dataset_id
    return rec

  if explicit_input.chain_from_dataset_id:
    return catalog[chain_from_dataset_id]

  candidates = turn_datasets  # 本 turn 仅
  if intent.bind == "fresh":
    candidates = [c for c in candidates if c.query_limit is None or c.result_rows > SLICE_MAX]
    if not candidates: return Error("请先 query_data 全量…")

  if intent.bind == "chain":
    candidates = [c for c in candidates if c.query_limit or c.result_rows <= SLICE_MAX]
    return max(candidates, key=created_at)  # 最近切片

  # auto: 打分
  scored = [(score(rec, intent), rec) for rec in candidates + optional_catalog_if_explicit_turn]
  return best if score > THRESHOLD else Error(...)
```

### 兼容性打分（示例维度）

| 检查 | 链式汇总 10 条 | 全班统计 |
|------|----------------|----------|
| `result_rows` ≤ 500 且 prior 有 `limit` | 加分 | 减分 |
| metrics 含 `count_distinct(student_ID)` 且 `result_rows` < 50 | 减分（像切片） | 需 `result_rows` 大或 `rows_scanned` 匹配 |
| `rows_scanned` 与 Class 规模接近 | — | 加分 |
| 同 `classes` + `resource` | 加分 | 加分 |
| 本 turn 创建的 ref | 加分 | 加分 |
| 上一 turn 的 ref 且未显式 dataset_id | **不自动选** | **不自动选** |

**不写死**：阈值 + 多特征加权；冲突时 **返回 Error + 候选列表**（最近 5 条 `dataset_id` 摘要），让模型改参或先 query。

---

## 5. 运行时策略（修订当前实现）

### 保留

- 每次 query 落盘 + `dataset_id`
- `begin_user_turn()` 清空工作集
- 同批 **先 query 后 aggregate**（避免 batch 内顺序颠倒）

### 调整（相对现有代码）

| 现有 | 问题 | 修订 |
|------|------|------|
| `working_active_ref` = 本 turn 最后一次 query | 并行 limit+全量时指向全量 | 拆成 `turn_datasets[]` + `resolve` 打分，不单用 last |
| 跨 turn 用 `pick` 优先 limit | 第二问误绑第一问切片 | **仅在本 turn** 或 `bind=chain` / 显式 id 时优先 limit |
| 自动把错误 ref 改成 working | 有时改对有时改错 | 仅在 **同 turn** 或 **兼容性提升** 时纠正；否则 **拒绝并说明** |
| `ref_corrected` 静默替换 | 掩盖模型错误 | 改为 `binding_decision: chain|fresh|explicit` + 理由 |

### 不建议

- ❌ 新 user_turn 一律拒绝旧 `result_ref`（场景 C 需要显式旧 id）
- ❌ 永远优先最小 `result_rows`（场景 B 需要全量）
- ❌ 永远优先最后一次 query（并行双 query 会错）

---

## 6. 工具契约（给模型）

### `query_data` 可选参数

- `as` / `label`：短标签，如 `class1_top10_lowest`
- 返回：`dataset_id`, `result_ref`, `result_rows`, `rows_scanned`, `query_limit`

### `aggregate_data`

- `input.result_ref` | `input.dataset_id`（显式，推荐）
- `input.chain_from_dataset_id`：声明续算上一数据集
- `bind`：`auto` | `chain` | `fresh`（可选）

### 错误可恢复

```
Error: 绑定失败：当前 ref 仅 10 行，无法代表 Class1 全班（rows_scanned=22960）。
| Next: 对本题执行 query_data(class=Class1, 省略 limit) 后使用新 dataset_id
| 或: aggregate(bind=chain, chain_from_dataset_id=ds_xxx) 若只需汇总该 10 条
```

---

## 7. 实施阶段

| 阶段 | 内容 |
|------|------|
| **P0** | 跨 turn **禁止** `working_active_ref` 自动注入；仅本 turn `turn_datasets` + 显式 id |
| **P1** | `compatibility(rec, metrics, bind)` + 不兼容时 **Error** 而非静默改正 |
| **P2** | `bind` / `chain_from_dataset_id` schema + prompt/skill |
| **P3** | ✅ `list_datasets` 工具 + 错误时 `format_catalog_hint` 摘要；可选 `as` 标签（未做） |

---

## 8. 用日志中的两题验证

| 题 | 正确绑定 |
|----|----------|
| Q1 最低 10 + 汇总这 10 条 | 同 ref `d297…`（10 行）；`bind=chain` 或 auto 高分 |
| Q2 全班概况 | **新** query 全量 → 新 `dataset_id`；auto 不得选 `d297…`（兼容性不及格） |

---

## 9. 一句话原则

**硬盘多份都保留；内存只负责「本题默认绑哪份」；跨题只能显式指名或在本题先 query；是否链式由意图（显式参数 + 兼容性）决定，不写死两条规则。**

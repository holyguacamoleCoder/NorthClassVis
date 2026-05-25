# 查询结果：内存工作集 + 硬盘落盘

## 分层

| 层 | 类比 | 存储 | 生命周期 |
|----|------|------|----------|
| **硬盘** | 磁盘文件 | `backend/.agent/task_outputs/query-results/*.json` | 会话内持久，可复盘 |
| **目录** | inode / 路径表 | `backend/.agent/sessions/<id>/datasets.jsonl` | 每条 query 一条 `dataset_id → result_ref` |
| **内存** | 工作集 / PC 寄存器 | `AnalysisToolContext.working_active_ref` | **仅当前教师一轮提问** |

## 规则

1. 每次 `query_data` 成功：**必定落盘** + 登记 `dataset_id` + 更新 `working_active_ref`。
2. 新用户消息：`begin_user_turn()` 清空工作集（不删硬盘文件）。
3. `aggregate_data` 绑定顺序：显式 `result_ref` / `dataset_id` → 本批最后一次 query（先 query 后 aggregate 执行）→ 本 turn 的 `working_active_ref`。
4. **不**跨 turn 自动用上一题的 ref；**不**用「最小 limit」猜切片（除非模型显式指定 ref）。

## 工具字段

- `query_data` 返回 `meta.result_ref`、`meta.dataset_id`、`meta.storage_layer=disk`、`meta.working_ref`。
- `aggregate_data` 可传 `input.dataset_id` 或 `input.result_ref`。

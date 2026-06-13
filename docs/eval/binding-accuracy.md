# Dataset Binding 准确率评测

> 生成时间：2026-06-11 07:49 UTC  
> 脚本：`backend/agent/eval/binding_accuracy.py`

## 指标定义

**绑定准确率** = `resolve_aggregate_binding` 输出与期望一致的场景占比。

- **正例**：`result_ref` / `dataset_id` 与标注一致且无 Error
- **负例（guard）**：应拒绝绑定（如跨 turn 静默续用）且返回含预期提示的 Error

**评测模式**：`BINDING_RESOLVER_DISABLE_LLM=1`（规则打分 + 启发式意图，无 live LLM）

## 结果摘要

| 指标 | 值 |
|------|-----|
| 场景数 N | 19 |
| 正确数 | 19 |
| **绑定准确率** | **100.0%** |

## 按类别

| 类别 | 正确/总数 | 准确率 |
|------|-----------|--------|
| `cross_turn_explicit` | 1/1 | 100.0% |
| `explicit` | 2/2 | 100.0% |
| `guard_negative` | 4/4 | 100.0% |
| `rule_bind` | 2/2 | 100.0% |
| `rule_correction` | 1/1 | 100.0% |
| `rule_scoring` | 3/3 | 100.0% |
| `rule_single` | 2/2 | 100.0% |
| `semantic_heuristic` | 4/4 | 100.0% |

## 失败场景

| 场景 | 原因 |
|------|------|
| — | 无 |

## 简历可用（一句话）

> 基于 N=19 个离线 binding 场景，aggregate 数据集绑定准确率 **100.0%**（规则 + 启发式 resolver，含跨 turn 硬规则拦截）。

## 局限性

- 离线评测，不经过真实 `query_data` 扫库
- 歧义场景使用启发式 resolver（`BINDING_RESOLVER_DISABLE_LLM=1`）；生产环境 LLM intent 路径未计入
- 多切片并存且教师话含「这些」时，启发式取最后一个 slice 候选（见代码 `heuristic_resolve`）

## 复现

```bash
cd H:/WORKDIR/NorthClassVision
python backend/agent/eval/binding_accuracy.py
```

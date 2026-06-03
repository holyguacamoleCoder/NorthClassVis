# Freeform Report Reference

适用：

- 窄时间窗口分析
- 专题备忘
- 教师临时提问
- 风险预警
- 教学复盘
- 课程诊断
- 非标准学情分析
- reports/notes/\*\*
- reports/<custom_dir>/\*\*

目标：

围绕特定问题快速形成可执行结论，而非生成完整标准报告。

---

## When To Use

满足以下任一情况：

- 用户未指定 Student / Class / Major 标准报告
- 分析对象跨多个粒度
- 关注某一专题问题
- 输出以决策支持为主
- 输出以备忘或记录为主

例如：

- 最近两周有哪些异常学生？
- 哪些题目需要复讲？
- 本周教学重点是什么？
- 数据里有哪些值得关注的现象？
- 风险学生追踪记录

---

## Recommended Structure

推荐结构：

```markdown
# <标题>

## scope

## key_findings

## actions

## evidence

## limitations
```

允许自由增删章节。

但必须保留：

```markdown
## Evidence

## Limitations
```

---

## Discovery-First Principle

优先围绕发现组织报告。

推荐流程：

发现问题
↓
收集证据
↓
形成结论
↓
提出行动

而不是：

套用模板
↓
填充内容

---

## Common Insight Types

自由报告优先关注：

### Trend

变化趋势

例如：

- 最近两周下降
- 活跃度持续增长

### Risk

风险信号

例如：

- 长期未提交
- 持续低表现

### Comparison

群体差异

例如：

- 班级差异
- 专业差异

### Weak Topics

薄弱知识点

例如：

- 高频错误题目
- 共同薄弱知识点

### Anomalies

异常现象

例如：

- 极端学生
- 突发波动

---

## Visualization Guidance

图表必须服务于当前问题。

### Trend Analysis

推荐：

- WeekView

### Question Diagnosis

推荐：

- QuestionView

### Peer Comparison

推荐：

- ScatterView
- PortraitView

### Structure Analysis

推荐：

- StudentView

禁止：

仅为了增加可视化而插入图表。

---

## Evidence Rules

所有关键结论必须来自：

- query_data
- aggregate_data

必须能够追溯。

禁止：

- 无证据推断
- 引用历史报告
- 引用未查询数据

---

## Action Rules

建议必须对应前文发现。

格式：

发现
↓
证据
↓
建议

避免：

- 通用教学建议
- 与数据无关的建议

例如：

❌ 加强课堂管理

❌ 提高学习兴趣

❌ 增强学习主动性

✅ 针对知识点A增加一次专项练习

✅ 对连续三周未提交学生进行跟踪

✅ 对错误率最高的题目安排复讲

---

## Chart Rules

所有 report-chart 必须满足：

- 对应明确结论
- params 与 build_visual_links 一致
- 图表下方有解释

允许：

- WeekView
- QuestionView
- ScatterView
- PortraitView

StudentView：

- 不使用 report-chart
- 仅通过 build_visual_links 展示

---

## Limitations Requirements

必须说明：

1. 时间窗口限制
2. 样本范围限制
3. 数据缺失情况
4. 分析假设

---

## Common Mistakes

### Wrong

为了凑结构套用 Student / Class / Major 模板

### Wrong

无证据直接下结论

### Wrong

图表与正文结论无关

### Wrong

只有图表没有解释

### Wrong

使用历史报告作为证据

### Wrong

缺失 Evidence 或 Limitations

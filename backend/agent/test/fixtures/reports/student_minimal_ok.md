# 个体学情诊断（fixture）

## scope

分析对象：J23517，Class2，软件工程；时间窗 week 13–15。

## summary

近三周 peak 均值呈下降趋势，链表相关题目错误集中。

## week_trend

周均 peak 从 week 13 的 2.1 降至 week 15 的 1.4（[@ref:query-results/week-trend.json]）。

```report-chart
{
  "view": "WeekView",
  "params": {
    "student_ids": ["J23517"],
    "week_range": [13, 15]
  }
}
```

上图展示该生各周提交活跃格子，与聚合趋势一致。

## student_structure

知识树中链表、指针分支得分偏低，其余章节中等。

## question_anchors

| 题目 | 错题次数 |
|------|----------|
| Question_101 | 3 |
| Question_205 | 2 |

```report-chart
{
  "view": "QuestionView",
  "params": {
    "title_ids": ["Question_101", "Question_205"]
  }
}
```

## peer_context

该生 peak 位于班级后 30% 区间，与同专业中等生相比偏弱。

## actions

针对链表知识点安排一次小测；错题 Question_101 课堂复讲。

## evidence

- 周趋势聚合 [@ref:query-results/week-trend.json]
- 错题统计 [@ref:query-results/questions.json]

## limitations

仅覆盖 week 13–15；未纳入课堂出勤数据。

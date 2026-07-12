# RAG 样例文档生成方案

> **目的**：项目当前只有 CSV 事实表，没有可直接 embedding 的文本资产。本文定义四类 RAG 文档的目录结构、字段契约、生成方式，并在 `data/rag/samples/` 各放 **1 份可运行样例**。  
> **关联**：`docs/plans/rag-chunking-strategy.md`

---

## 1. 目录结构

```text
data/rag/
├── samples/                          # 各场景样例（人工审阅 / 单测 fixture）
│   ├── profiles/
│   ├── questions/
│   ├── knowledge/
│   └── majors/
├── profiles/                         # 批量产物：离线学生画像（1 人 1 文件）
├── questions/                        # 批量产物：纯题目内容（题干 / 解析）
├── knowledge/                        # 批量产物：纯知识点内容（定义 / 概念）
└── majors/                           # 批量产物：专业培养方案（长文，入库前再切分）
```

**文件命名约定**

| 场景 | 路径模式 | 示例 |
|------|---------|------|
| 学生画像 | `profiles/{student_ID}.md` | `profiles/bfc3a5cb3b9c29f08176.md` |
| 单题 | `questions/{title_ID}.md` | `questions/Question_5fgqjSBwTPG7KUV3it6O.md` |
| 子知识点 | `knowledge/{sub_knowledge}.md` | `knowledge/g7R2j_e0v1yls8.md` |
| 专业方案 | `majors/{major}.md` | `majors/J40192.md` |

---

## 2. 统一文件格式（YAML frontmatter + Markdown 正文）

所有 RAG 文档采用同一外壳，便于解析与入库：

```yaml
---
doc_type: student_profile | question | knowledge | major_curriculum
chunk_strategy: none | recursive
# …场景专属元数据…
generated_at: "2026-07-12"
source: offline_etl | manual | llm_assisted
---

（供 embedding 的自然语言正文）
```

- **`chunk_strategy: none`**：整文件作为一个 Document 入库。
- **`chunk_strategy: recursive`**：入库前用 RecursiveCharacterTextSplitter 切分；样例文件仍保持完整长文，切分结果只在索引阶段产生。

---

## 3. 四类场景：生成逻辑 + 样例索引

### 场景 A — 离线学生画像（不分块）

| 项 | 说明 |
|----|------|
| **输入** | `SubmitRecord` + `StudentInfo` + `TitleInfo`，经 `week_aggregation` 聚合 |
| **触发** | 离线 ETL（建议每周一次） |
| **输出** | 每人 1 个 `.md`，200–400 tokens |
| **样例** | [`data/rag/samples/profiles/bfc3a5cb3b9c29f08176.md`](../../data/rag/samples/profiles/bfc3a5cb3b9c29f08176.md) |

**生成步骤（伪代码）**

```python
for student_id in all_students:
    stats = aggregate(student_id, weeks=ALL)
    text = render_profile_template(stats)  # 自然语言，非 JSON  dump
    write(f"data/rag/profiles/{student_id}.md", frontmatter + text)
```

**正文必含字段**：身份（性别/年龄/专业/班级）、周趋势摘要、Top3 薄弱/强项知识点、行为特征（耗时/memory）、班级/专业相对位置。

---

### 场景 B — 单道题目（不分块，纯内容）

| 项 | 说明 |
|----|------|
| **定位** | **静态题库**：只存「考什么、怎么解」，不存学情分析 |
| **输入** | 人工 / LLM 撰写的题干、要求、示例、参考答案、解析 |
| **触发** | 题目首次录入或题干修订时 |
| **输出** | 每题 1 个 `.md`，100–400 tokens |
| **样例** | [`data/rag/samples/questions/Question_5fgqjSBwTPG7KUV3it6O.md`](../../data/rag/samples/questions/Question_5fgqjSBwTPG7KUV3it6O.md) |

**frontmatter 仅保留索引字段**（来自 `Data_TitleInfo.csv`）：`title_ID`, `score`, `knowledge`, `sub_knowledge`, `question_type`。

**正文允许包含**

- 题干、输入输出要求、示例用例
- 参考答案、官方解析、通用易错点（不绑定具体班级或 `state` 枚举）

**正文禁止包含**（属于事后分析，运行时由工具产出）

- 某班尝试次数、正确率、错误状态分布
- 「Class2 薄弱」「需重点关注」等诊断结论
- 关联学生、关联提交记录

**生成步骤**

```python
for title_id in title_catalog:
    meta = load_title_info(title_id)           # CSV：score, knowledge, sub_knowledge
    body = load_question_body(title_id)        # 人工 / LLM / 外部题库
    write(f"data/rag/questions/{title_id}.md", frontmatter(meta) + body)
    # 学情分析不在此步骤；需要时 Agent 调 aggregate_data(title_ID, class=...)
```

**注意**：`Data_TitleInfo.csv` 仅有 ID 与知识点标签，**题干正文需新建内容源**（本方案用样例占位，后续可扩 CSV 列或 JSON 题库）。

---

### 场景 C — 子知识点说明（不分块，纯内容）

| 项 | 说明 |
|----|------|
| **定位** | **静态知识库**：只存「学什么、概念是什么」，不存班级表现 |
| **输入** | 教学大纲 / 教材章节 / LLM 根据知识点 ID 扩写 |
| **触发** | 知识点树变更时 |
| **输出** | 每个 `sub_knowledge` 1 个 `.md` |
| **样例** | [`data/rag/samples/knowledge/g7R2j_e0v1yls8.md`](../../data/rag/samples/knowledge/g7R2j_e0v1yls8.md) |

**frontmatter 仅保留索引字段**：`knowledge`, `sub_knowledge`, `parent_knowledge`, `label_zh`。

**正文允许包含**

- 中文名称、定义、核心概念、前置知识（课程层级关系）
- 典型题型描述（抽象表述，不引用具体班级数据）

**正文禁止包含**

- 各班级尝试次数、正确率、薄弱排名
- 教学干预建议、报告章节引用
- 运行时才能确定的「关联题目表现」

**生成步骤**

```python
for sub_knowledge in knowledge_tree:
    meta = load_knowledge_meta(sub_knowledge)
    body = load_knowledge_body(sub_knowledge)   # 教材 / 大纲 / LLM
    write(f"data/rag/knowledge/{sub_knowledge}.md", frontmatter(meta) + body)
    # 哪些题属于该知识点：运行时 join TitleInfo + SubmitRecord
```

---

### 场景 D — 专业培养方案（递归分块）

| 项 | 说明 |
|----|------|
| **输入** | 专业课程体系、能力矩阵（人工撰写或导入） |
| **触发** | 专业方案修订时 |
| **输出** | 每个 `major` 1 个长 `.md`（1500+ tokens）；入库时切分 |
| **样例** | [`data/rag/samples/majors/J40192.md`](../../data/rag/samples/majors/J40192.md) |

**切分参数（入库阶段）**

```python
RecursiveCharacterTextSplitter(
    chunk_size=500,      # tokens
    chunk_overlap=50,
    separators=["\n\n", "\n", "。", " "],
)
```

**每块附加元数据**：`major`, `chunk_index`, `total_chunks`, `section_heading`（若可解析）。

---

## 4. 批量生成路线图

| 阶段 | 范围 | 方式 |
|------|------|------|
| **P0 样例** | 每场景 1 文件 | 人工 + 真实 ID/统计（已完成 → `samples/`） |
| **P1 半自动** | 画像 + 学情字段 | 脚本从 CSV 聚合，LLM 仅润色自然语言 |
| **P2 内容补全** | 题目 + 知识点 | 教师提供大纲 / LLM 按 ID 扩写，人工抽检 |
| **P3 入库** | 全量 | embedding → 向量库，Agent 增加 `search_*` 工具 |

**建议优先顺序**：画像（P1）→ 子知识点（P2）→ 单题（P2）→ 专业方案（P2，量最少）。

---

## 5. 与现有系统的关系：静态内容 vs 事后分析

```text
                    ┌── data/rag/questions/   （纯题干，静态）
                    ├── data/rag/knowledge/   （纯概念，静态）
静态内容 ──embedding──► 向量库 ◄── search_questions / search_knowledge
                    │
CSV 事实表 ──aggregate──► query_data / aggregate_data（运行时）
                    │
                    └── 学生画像 ETL ──► data/rag/profiles/（离线分析产物，另线）
```

**职责分离**

| 资产 | 存什么 | 不存什么 |
|------|--------|---------|
| 题目 `.md` | 题干、示例、参考答案、官方解析 | 班级正确率、错误 state 分布 |
| 知识点 `.md` | 定义、概念、前置知识、抽象题型 | 班级薄弱统计、教学建议 |
| 运行时工具 | 尝试次数、正确率、周趋势、学生名单 | — |

Agent 典型链路：

1. RAG 召回题目/知识点**语义**（「二分查找考什么」「边界条件指什么」）
2. `aggregate_data` 拉**学情数字**（Class2 在该题正答率多少）
3. LLM 在会话中**即时综合**，而非读取预写好的分析文档

- 题目/知识点正文可 LLM 辅助撰写，标注 `source: llm_assisted` 并人工抽检。
- 学生画像仍属离线分析产物（场景 A），与纯内容题库分开维护。

---

## 6. 样例文件清单

| 场景 | 文件 | 分块策略 |
|------|------|---------|
| A 学生画像 | `samples/profiles/bfc3a5cb3b9c29f08176.md` | none |
| B 单道题目 | `samples/questions/Question_5fgqjSBwTPG7KUV3it6O.md` | none |
| C 子知识点 | `samples/knowledge/g7R2j_e0v1yls8.md` | none |
| D 专业方案 | `samples/majors/J40192.md` | recursive（入库时） |

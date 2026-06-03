# NorthClassVision 数据工作区目录

> **定位**：本文件是数据资产的**元数据说明**（catalog），不是业务交付报告。  
> Agent 产出报告请写入 `data/reports/`。  
> **运行时状态**（会话、审计、工具大块输出等）存放在 `backend/.agent/`，不在 `data/` 内，Agent 工具无法通过 `read_file` 访问。  
> **注入策略**：`SessionStart` hook 注入精简「数据索引」（resource 表 + 契约路径）；完整字段见下文。Agent 在 analyze/produce 下按需 `read_file` 本文件（可带 `limit` 分段阅读）。

## 快速索引（Session 摘要用）

| 资产 | 路径 | 用途 |
|------|------|------|
| 学生主数据 | `Data_StudentInfo.csv` | 学生属性（专业、性别、年龄） |
| 题目主数据 | `Data_TitleInfo.csv` | 题目分值、知识点层级 |
| 提交记录 | `Data_SubmitRecord/SubmitRecord-{Class}.csv` | 按班级的答题/提交明细（学业分析核心事实表） |
| 本目录 | `meta/data_catalog.md` | 数据结构说明（只读参考） |
| 报告写作规范 | `skills/report-writing/`（SKILL + reference.md） | produce 自动注入 `report-writing`；标准总览/诊断再 `analysis-*`；报告一律写 `reports/` |

**关联键**：`student_ID`（提交记录 <-> 学生）、`title_ID`（提交记录 <-> 题目）。

**Agent 读取策略**：原始 CSV 只读且**禁止** Agent `read_file` 打开；学业分析用逻辑 resource（`meta/resource_registry.yaml`）经 `inspect_schema` / `query_data` / `aggregate_data`。人工调试若必须读 CSV，须带 `limit`，勿一次全量。

---

## 1. Data_StudentInfo.csv

- **格式**：CSV（逗号分隔，UTF-8）
- **粒度**：一名学生一行
- **字段**：
  - `index`：行序号
  - `student_ID`：学生唯一标识（与提交记录关联）
  - `sex`：性别
  - `age`：年龄
  - `major`：专业代码
- **示例**：
  ```
  index,student_ID,sex,age,major
  1,8b6d1125760bd3939b6e,female,24,J23517
  2,63eef37311aaac915a45,female,21,J87654
  ```

## 2. Data_TitleInfo.csv

- **格式**：CSV
- **粒度**：一道题目一行
- **字段**：
  - `index`：行序号
  - `title_ID`：题目唯一标识（与提交记录关联）
  - `score`：题目分值/权重
  - `knowledge`：知识点
  - `sub_knowledge`：子知识点
- **示例**：
  ```
  index,title_ID,score,knowledge,sub_knowledge
  1,Question_VgKw8PjY1FR6cm2QI9XW,1,r8S3g,r8S3g_l0p5viby
  ```

## 3. Data_SubmitRecord/（按班级的提交记录）

- **格式**：每个班级一个 CSV，命名 `SubmitRecord-{ClassName}.csv`（如 `SubmitRecord-Class1.csv` … `SubmitRecord-Class15.csv`）
- **粒度**：一次提交/作答一行（同一学生对多题有多行）
- **体积**：单文件约 1.5～2.5 MB；Agent 经 `submit_record` resource 查询，勿 `read_file` 本文件
- **字段**：
  - `index`：行序号
  - `class`：班级名（与文件名一致，如 `Class1`）
  - `time`：提交时间（Unix 时间戳，浮点）
  - `state`：作答状态（如 `Absolutely_Correct` 等）
  - `score`：本次得分
  - `title_ID`：题目 ID（关联 `Data_TitleInfo.csv`）
  - `method`：解题方法标识
  - `memory`：内存相关指标（后端会数值化）
  - `timeconsume`：耗时（后端会按 `student_ID`+`knowledge` 分组填充缺失）
  - `student_ID`：学生 ID（关联 `Data_StudentInfo.csv`）
- **示例**：
  ```
  index,class,time,state,score,title_ID,method,memory,timeconsume,student_ID
  0,Class1,1704209872.0,Absolutely_Correct,3,Question_bumGRTJ0c8p4v5D6eHZa,Method_...,320,3,8b6d1125760bd3939b6e
  ```
- **后端用法**（`backend/core/data_loader.py`）：按班级列表 `concat` 多个 `SubmitRecord-*.csv`，再与 `Data_TitleInfo` / `Data_StudentInfo` 按 `title_ID` 或 `student_ID` 合并。

## 4. 其他文件

- `first_dataDes.docx`：人工数据说明文档（可选参考，勿当作机器可读表）
- `test.txt`：测试用文本，非生产数据集

## 5. 学业分析的数据组合建议（Agent）

1. `student_info` / `title_info` / `submit_record`（`classes`）/ `week_aggregation` — 见 `resource_registry.yaml`
2. 统计：`query_data`（全量省略 `limit`）→ `aggregate_data`（`input.result_ref`）；人数用 `count_distinct(student_ID)`
3. 报告与图表：produce 模式写 `reports/`，配合 `build_visual_links` 与 ` ```report-chart ` 块
4. 关联键：`student_ID`、`title_ID`、`class`、`major`

## 6. 写入与权限

- **只读**：`Data_*.csv`、`Data_SubmitRecord/**`
- **可写（produce 模式）**：`reports/**`、`exports/**`

## 7. 学业分析契约（Agent）

> CSV 只读不变。契约：`meta/analysis_ontology.yaml`、`meta/visual_link_contract.yaml` 等；逻辑资源 **`meta/resource_registry.yaml`**。produce 注入 `report-writing`；标准个体/班/专业再加 `analysis-*`；所有 Markdown 报告在 `reports/`（含 `reports/notes/`）；勿 read 旧稿。

**Phase 3 薄适配工具**：`get_current_filter_context`（当前 Nav/会话分析范围，不算指标）与 `build_visual_links`（按 `visual_link_contract.yaml` 校验五视图跳转参数，不渲染图表）。

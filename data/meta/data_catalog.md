# NorthClassVision 数据工作区目录

> **定位**：本文件是数据资产的**元数据说明**（catalog），不是业务交付报告。  
> Agent 产出报告请写入 `data/reports/`。  
> **运行时状态**（会话、审计、工具大块输出等）存放在 `backend/.agent/`，不在 `data/` 内，Agent 工具无法通过 `read_file` 访问。  
> **注入策略**：`SessionStart` hook 会注入本文的摘要；完整字段与关联见下文。按需 `read_file` 路径 `meta/data_catalog.md`（可带 `limit` 分段阅读）。

## 快速索引（Session 摘要用）

| 资产 | 路径 | 用途 |
|------|------|------|
| 学生主数据 | `Data_StudentInfo.csv` | 学生属性（专业、性别、年龄） |
| 题目主数据 | `Data_TitleInfo.csv` | 题目分值、知识点层级 |
| 提交记录 | `Data_SubmitRecord/SubmitRecord-{Class}.csv` | 按班级的答题/提交明细（学业分析核心事实表） |
| 本目录 | `meta/data_catalog.md` | 数据结构说明（只读参考） |

**关联键**：`student_ID`（提交记录 <-> 学生）、`title_ID`（提交记录 <-> 题目）。

**读取策略**：`Data_*.csv` 与 `Data_SubmitRecord/*.csv` 均为只读；体积大，探索时 `read_file` 必须带 `limit`；学业报告通常先选 1～2 个班级文件抽样，勿一次读全量。

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
- **体积**：单文件约 1.5～2.5 MB，**禁止无 limit 全量 read**
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

## 5. 学业情况报告的数据组合建议

1. `Data_StudentInfo.csv`：样本学生画像（专业、年龄分布）
2. `Data_TitleInfo.csv`：知识点与分值结构
3. `Data_SubmitRecord/SubmitRecord-Class{N}.csv`：选一个或多个班级的提交明细（得分、正误、耗时）
4. 合并逻辑：以 `student_ID`、`title_ID` 为键做叙述性汇总（当前 agent 无 SQL/聚合引擎，需抽样 + 分班级阅读）

## 6. 写入与权限

- **只读**：`Data_*.csv`、`Data_SubmitRecord/**`
- **可写（produce 模式）**：`reports/**`、`exports/**`

## 7. 学业分析契约（Agent）

> CSV 只读不变。契约共 **4 处**：`meta/analysis_ontology.yaml`（含个体六章）、`meta/visual_link_contract.yaml`、`meta/metrics/_index.yaml`、`backend/agent/contracts/tabular_result.schema.json`。逻辑资源注册表：**`meta/resource_registry.yaml`**（Phase 1，`backend/agent/data/registry.py` 加载）。Phase 表见 `docs/plans/agentic-analysis-roadmap.md`。

**Phase 3 薄适配工具**：`get_current_filter_context`（当前 Nav/会话分析范围，不算指标）与 `build_visual_links`（按 `visual_link_contract.yaml` 校验五视图跳转参数，不渲染图表）。

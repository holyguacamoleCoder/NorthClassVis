# Skills 分析分层维护说明

## 目录结构（Cursor 标准）

```text
skills/
├── report-writing/       # produce 通用层（凡写 reports/）
│   ├── SKILL.md          # 短入口
│   └── references/       # tier 规范（load_reference 按需加载）
│       ├── student.md
│       ├── class.md
│       ├── major.md
│       └── freeform.md
├── data-exploration/     # 查数工作流
└── …
```

- **不再使用** `skills/reference/*.md` 伪 skill 目录。
- `SkillRegistry`：仅 `skills/**/SKILL.md` 正文；`report-delivery` → `report-writing` 别名兼容。
- 参考文档经 `load_reference` 注入 tool result（pin，不参与上下文压缩）。

## 加载策略

| 模式 | 行为 |
|------|------|
| **produce** | `report-writing` 自动登记；首轮合成 pin 的 `load_skill` tool result |
| **produce + 标准总览/诊断** | 再 `load_reference("student"\|"class"\|"major")` |
| **produce + 通用报告**（窄窗、备忘） | 仅 `report-writing` + 可选 `freeform` |
| **analyze** | 不自动注入 report-writing；可 `load_skill` / `load_reference` |

## Prompt 分工

- `prompts.py`：模式边界、路由表、**已加载名称列表**（无 SKILL 全文）
- `load_skill` / `load_reference` tool result：SKILL / 参考全文（`_agent_meta.compact_policy=pin`）

## `reports/` 政策

仅 **写入**，禁止 `read_file` 参考旧稿。

## 测试

```bash
cd backend/agent && py -3.11 -m pytest test/test_skills.py test/test_session_prompt_pins.py test/test_context_compact.py -q
```

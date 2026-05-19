from dataclasses import dataclass, field

MAX_ITEMS = 12
MAX_ROUND_SINCE_UPDATE = 3

# content：这一步要做什么
# status: "pending" | "in_progress" | "completed"
# activeForm：当它正在进行中时，可以用更自然的进行时描述
@dataclass
class PlanItem:
    content: str
    status: str = field(default="pending")
    active_form: str = ""
    # id: str = field(default_factory=lambda: str(uuid.uuid4()))

# round_since_update: 连续多少轮过去了，模型还没有更新这份计划
@dataclass
class PlaningState:
    items: list[PlanItem] = field(default_factory=list)
    round_since_update: int = 0

class TodoManager:
    def __init__(self):
        self.state = PlaningState()
    def update(self, items: list) -> str:
        # 模型更新当前计划
        if len(items) > MAX_ITEMS:
            raise ValueError(f"Too many items: {len(items)} > {MAX_ITEMS}")
        normalized_items = []
        in_progress_count = 0
        for index, raw_item in enumerate(items):
            content = str(raw_item.get("content", "")).strip()
            status = str(raw_item.get("status", "pending")).lower()
            active_form = str(raw_item.get("active_form", "")).strip()
            if not content:
                raise ValueError(f"Item {index} has no content")
            if status not in ["pending", "in_progress", "completed"]:
                raise ValueError(f"Item {index} has invalid status: {status}")
            if status == "in_progress":
                in_progress_count += 1
            item = PlanItem(
                content=content,
                status=status,
                active_form=active_form,
            )
            normalized_items.append(item)

        # 暂时设置：最多只能有一个进行中的计划
        if in_progress_count > 1:
            raise ValueError("Too many in-progress items")
        self.state.items = normalized_items
        self.state.round_since_update = 0
        return self.render()

    def render(self) -> str:
        # 把计划变成可读文本
        if not self.state.items:
            return "No session plan yet."
        lines = []
        for item in self.state.items:
            marker = {
                "pending": "[ ]",
                "in_progress": "[>]",
                "completed": "[√]",
            }[item.status]
            line = f"{marker} {item.content}"
            if item.status == "in_progress" and item.active_form:
                line += f" ({item.active_form})"
            lines.append(line)
        completed = sum(1 for item in self.state.items if item.status == "completed")
        lines.append(f"Completed: {completed}/{len(self.state.items)}")
        return "\n".join(lines)

    def reminder(self) -> str | None:
        # 给模型提供提醒，让它知道当前计划状态
        # 主要是提醒模型，哪些计划还没有进行
        if not self.state.items:
            return None
        if self.state.round_since_update < MAX_ROUND_SINCE_UPDATE:
            return None
        return "<reminder>Refresh the session plan to keep track of progress.</reminder>"

    def mark_round_passed(self) -> None:
        self.state.round_since_update += 1


todo_manager = TodoManager()


def reset_todo_state() -> None:
    todo_manager.state = PlaningState()


def export_todo_snapshot() -> tuple[list[dict[str, str]], int]:
    items: list[dict[str, str]] = []
    for item in todo_manager.state.items:
        row: dict[str, str] = {
            "content": item.content,
            "status": item.status,
        }
        if item.active_form:
            row["active_form"] = item.active_form
        items.append(row)
    return items, todo_manager.state.round_since_update


def apply_todo_snapshot(items: list[dict[str, str]], round_since_update: int = 0) -> None:
    reset_todo_state()
    if not items:
        todo_manager.state.round_since_update = round_since_update
        return
    try:
        todo_manager.update(items)
    except ValueError:
        todo_manager.state.round_since_update = round_since_update
        return
    todo_manager.state.round_since_update = round_since_update


def run_todo_write(items: list) -> str:
    return todo_manager.update(items)


def get_todo_reminder() -> str | None:
    return todo_manager.reminder()


def mark_round_without_todo_update() -> None:
    todo_manager.mark_round_passed()

TODO_MANAGER_SCHEMA = {
  "type": "function",
  "function": {
      "name": "todo_write",
      "description": "Rewrite the current session plan for multi-step work.",
      "parameters": {
        "type": "object",
        "properties": {
          "items": {
                "type": "array",
                "items": {
                  "type": "object",
                  "properties": {
                    "content": {"type": "string"},
                    "status": {
                        "type": "string",
                        "enum": ["pending", "in_progress", "completed"],
                    },
                    "active_form": {
                        "type": "string",
                        "description": "Optional present-continuous label.",
                    },
                  },
                  "required": ["content", "status"],
                },
            },
        },
        "required": ["items"],
      },
  }
}

"""
请先使用 todo_write 制定并维护一个 5 步以内的分析计划（必须包含 in_progress / pending / completed 状态，并在每完成一步后更新 todo_write）。

任务：基于 data/Data_StudentInfo.csv 和 data/Data_TitleInfo.csv 做一个简要学习表现分析，输出：
1) 数据概览（行数、字段、缺失值概况）；
2) 学生总体正确率分布（给出均值/中位数/分位数）；
3) 按题目维度统计最难和最易的前 5 题；
4) 给出 3 条可执行教学建议（基于上面的统计结论）；
5) 最后输出一段“计划完成情况总结”（引用 todo_write 的最终状态）。

要求：
- 每一步开始前或结束后都调用 todo_write 更新状态；
- 遇到异常（如字段不存在）要在 todo_write 中标记并调整后续计划；
- 结论要有对应的数据依据，不要只给主观判断。
"""
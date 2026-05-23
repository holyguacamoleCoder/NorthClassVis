from dataclasses import dataclass, field

MAX_ITEMS = 12
MAX_ROUND_SINCE_UPDATE = 3

_TODO_EXAMPLE = (
    '{"content":"inspect submit_record_joined for Class1","status":"in_progress",'
    '"active_form":"Checking schema"}'
)


@dataclass
class PlanItem:
    content: str
    status: str = field(default="pending")
    active_form: str = ""
    acceptance: str = ""


@dataclass
class PlaningState:
    items: list[PlanItem] = field(default_factory=list)
    round_since_update: int = 0


class TodoManager:
    def __init__(self):
        self.state = PlaningState()

    def update(self, items: list) -> str:
        if len(items) > MAX_ITEMS:
            raise ValueError(f"Too many items: {len(items)} > {MAX_ITEMS}")
        normalized_items = []
        in_progress_count = 0
        for index, raw_item in enumerate(items):
            content = str(raw_item.get("content", "")).strip()
            status = str(raw_item.get("status", "pending")).lower()
            active_form = str(raw_item.get("active_form", "")).strip()
            acceptance = str(raw_item.get("acceptance", "")).strip()
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
                acceptance=acceptance,
            )
            normalized_items.append(item)

        if in_progress_count > 1:
            raise ValueError("Too many in-progress items (at most one allowed)")
        self.state.items = normalized_items
        self.state.round_since_update = 0
        return self.render()

    def render(self) -> str:
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
            if item.acceptance:
                line += f"\n    Acceptance: {item.acceptance}"
            lines.append(line)
        completed = sum(1 for item in self.state.items if item.status == "completed")
        lines.append(f"Completed: {completed}/{len(self.state.items)}")
        return "\n".join(lines)

    def reminder(self) -> str | None:
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
        if item.acceptance:
            row["acceptance"] = item.acceptance
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


def _plan_progress_header() -> str:
    items = todo_manager.state.items
    if not items:
        return "[Plan updated: empty]"
    completed = sum(1 for item in items if item.status == "completed")
    return f"[Plan updated: {completed}/{len(items)} completed]"


def run_todo_write(items: list | None = None) -> str:
    if items is None:
        return (
            "Error: items is required | Example: items=["
            f"{_TODO_EXAMPLE}, {{\"content\":\"…\",\"status\":\"pending\"}}]"
        )
    try:
        body = todo_manager.update(items)
        return f"{_plan_progress_header()}\n{body}"
    except ValueError as exc:
        return (
            f"Error: {exc} | Next: fix items—max {MAX_ITEMS}, one in_progress, "
            f"valid status pending|in_progress|completed | Example: {_TODO_EXAMPLE}"
        )


def get_todo_reminder() -> str | None:
    return todo_manager.reminder()


def mark_round_without_todo_update() -> None:
    todo_manager.mark_round_passed()


def plan_is_stale_after_data() -> bool:
    """True when a plan exists but work remains (needs refresh after data tools)."""
    items = todo_manager.state.items
    if not items:
        return False
    completed = sum(1 for item in items if item.status == "completed")
    if completed >= len(items):
        return False
    return True

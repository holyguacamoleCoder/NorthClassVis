from dataclasses import dataclass, field


@dataclass
class CompactState:
    has_compacted: bool = False
    last_summary: str = ""
    recent_files: list[str] = field(default_factory=list)


def track_recent_file(state: CompactState, path: str, *, max_files: int = 5) -> None:
    if not path:
        return
    if path in state.recent_files:
        state.recent_files.remove(path)
    state.recent_files.append(path)
    if len(state.recent_files) > max_files:
        state.recent_files[:] = state.recent_files[-max_files:]

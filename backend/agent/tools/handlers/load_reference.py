from __future__ import annotations

from skills.references import read_reference_text, skills_dir
from skills.tool_result import format_reference_active_result, format_reference_load_result


def run_load_reference(
    name: str | None = None,
    *,
    _loaded_references: set[str] | None = None,
) -> str:
    loaded = _loaded_references if _loaded_references is not None else set()
    if not name or not str(name).strip():
        return (
            "Error: reference name is required | Next: pass a file name like "
            "'student'/'class'/'major'/'freeform' or a relative path under skills/."
        )

    found = read_reference_text(str(name))
    if found is not None:
        ref_id, text = found
        if ref_id in loaded:
            return format_reference_active_result(ref_id)
        loaded.add(ref_id)
        return format_reference_load_result(ref_id, text)

    root = skills_dir().as_posix()
    return (
        f"Error: Unknown reference '{name}' under {root} | Next: use one of "
        "'student', 'class', 'major', 'freeform' or an exact relative path."
    )

"""Report deliverable tools (produce mode)."""

from __future__ import annotations

from report.review import format_review_for_tool_result, review_report

from .base_tool import _format_tool_error, _safe_path


def run_review_report(
    path: str,
    validation_level: str | None = None,
    *,
    _analysis_context=None,
) -> str:
    """
    Cross-section consistency review for an on-disk report.
    Returns structured issues only — not the full markdown body.
    """
    try:
        fp = _safe_path(path)
        rel = str(path).strip().replace("\\", "/")
        if not rel.startswith("reports/") or not rel.endswith(".md"):
            return (
                "Error: review_report only supports reports/**/*.md paths "
                f"(got {path!r})"
            )
        if not fp.is_file():
            return (
                f"Error: File not found: {path} | Next: write_file skeleton first, "
                "then fill sections before review"
            )
        source = fp.read_text(encoding="utf-8")
        level = (validation_level or "deliver").strip().lower()
        if level not in ("draft", "deliver", "strict"):
            level = "deliver"
        result = review_report(
            source,
            path=rel,
            analysis_context=_analysis_context,
            validation_level=level,
        )
        return format_review_for_tool_result(result)
    except UnicodeDecodeError:
        return f"Error: File is not valid UTF-8: {path}"
    except ValueError as exc:
        return _format_tool_error(exc, path)
    except Exception as exc:
        return _format_tool_error(exc, path)

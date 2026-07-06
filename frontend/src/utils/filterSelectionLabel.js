/**
 * Human-readable label for checkbox filter dropdowns (Class / Major).
 * Replaces opaque "Part" / "All" with actual selection summary.
 */

export function formatFilterSelectionLabel(items, options = {}) {
  const {
    maxVisible = 2,
    allLabel = '全部',
    noneLabel = '未选',
    separator = '、',
  } = options

  if (!Array.isArray(items) || items.length === 0) return noneLabel

  const selected = items.filter((item) => item && item.checked).map((item) => item.text)
  if (selected.length === 0) return noneLabel
  if (selected.length === items.length) return allLabel
  if (selected.length <= maxVisible) return selected.join(separator)
  const head = selected.slice(0, maxVisible).join(separator)
  return `${head}${separator}等${selected.length}项`
}

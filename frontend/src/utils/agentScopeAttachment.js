/** Helpers for composer / message scope attachment chips. */

export function shortStudentId(id, head = 6, tail = 4) {
  const s = String(id || '')
  if (s.length <= head + tail + 1) return s
  return `${s.slice(0, head)}…${s.slice(-tail)}`
}

export function hasScopeContent(scope) {
  if (!scope || typeof scope !== 'object') return false
  const ids = Array.isArray(scope.selected_student_ids)
    ? scope.selected_student_ids.filter(Boolean)
    : []
  if (ids.length) return true
  const classes = Array.isArray(scope.classes) ? scope.classes.filter(Boolean) : []
  if (classes.length) return true
  const majors = Array.isArray(scope.majors) ? scope.majors.filter(Boolean) : []
  if (majors.length) return true
  const week = scope.week_range
  if (Array.isArray(week) && week.length >= 2 && week[0] != null && week[1] != null) {
    return true
  }
  return false
}

export function formatScopeAttachmentMeta(scope, ui = {}) {
  if (!scope) return ''
  const ids = Array.isArray(scope.selected_student_ids)
    ? scope.selected_student_ids.filter(Boolean)
    : []
  const parts = []
  if (ids.length) {
    const labelFn = ui.scopeAttachStudents || ((n) => `已选 ${n} 人`)
    parts.push(labelFn(ids.length))
  }
  const week = scope.week_range
  if (Array.isArray(week) && week.length >= 2 && week[0] != null && week[1] != null) {
    parts.push(`第 ${week[0]}–${week[1]} 周`)
  }
  const classes = Array.isArray(scope.classes) ? scope.classes.filter(Boolean) : []
  if (classes.length) {
    parts.push(classes.slice(0, 2).join('、') + (classes.length > 2 ? '…' : ''))
  }
  const majors = Array.isArray(scope.majors) ? scope.majors.filter(Boolean) : []
  if (majors.length) {
    parts.push(majors.slice(0, 2).join('、') + (majors.length > 2 ? '…' : ''))
  }
  return parts.join(' · ') || (ui.scopeAttachEmpty || '当前范围')
}

export function cloneScopeAttachment(scope) {
  if (!scope || typeof scope !== 'object') return null
  const out = {}
  if (Array.isArray(scope.selected_student_ids)) {
    out.selected_student_ids = [...scope.selected_student_ids].filter(Boolean)
  } else {
    out.selected_student_ids = []
  }
  if (Array.isArray(scope.classes)) {
    out.classes = [...scope.classes].filter(Boolean)
  }
  if (Array.isArray(scope.majors)) {
    out.majors = [...scope.majors].filter(Boolean)
  }
  if (Array.isArray(scope.week_range) && scope.week_range.length >= 2) {
    out.week_range = [scope.week_range[0], scope.week_range[1]]
  }
  return hasScopeContent(out) ? out : null
}

export function buildScopeAttachmentFromContext(context) {
  if (!context || typeof context !== 'object') return null
  const ids = Array.isArray(context.selected_student_ids)
    ? context.selected_student_ids.map((x) => String(x || '').trim()).filter(Boolean)
    : []
  const out = { selected_student_ids: ids }
  if (Array.isArray(context.classes) && context.classes.length) {
    out.classes = context.classes.map((x) => String(x || '').trim()).filter(Boolean)
  }
  if (Array.isArray(context.majors) && context.majors.length) {
    out.majors = context.majors.map((x) => String(x || '').trim()).filter(Boolean)
  }
  if (Array.isArray(context.week_range) && context.week_range.length >= 2) {
    out.week_range = [context.week_range[0], context.week_range[1]]
  }
  return hasScopeContent(out) ? out : null
}

export function scopeAttachmentKey(scope) {
  if (!scope) return ''
  const ids = (scope.selected_student_ids || []).join(',')
  const week = Array.isArray(scope.week_range) ? scope.week_range.join('-') : ''
  const classes = (scope.classes || []).join(',')
  const majors = (scope.majors || []).join(',')
  return `${ids}|${week}|${classes}|${majors}`
}

/** Helpers for composer / message scope attachment chips. */

export function shortStudentId(id, head = 6, tail = 4) {
  const s = String(id || '')
  if (s.length <= head + tail + 1) return s
  return `${s.slice(0, head)}…${s.slice(-tail)}`
}

function cleanStrList(value) {
  if (!Array.isArray(value)) return []
  return value.map((x) => String(x || '').trim()).filter(Boolean)
}

export function emptyComposerExtras() {
  return {
    knowledge_ids: [],
    title_ids: [],
    dataset: null,
    view_snapshot: null,
    report: null,
  }
}

export function hasComposerExtras(extras) {
  if (!extras || typeof extras !== 'object') return false
  if (cleanStrList(extras.knowledge_ids).length) return true
  if (cleanStrList(extras.title_ids).length) return true
  if (extras.dataset?.run_id || extras.dataset?.dataset_id) return true
  if (extras.view_snapshot?.view) return true
  if (extras.report?.path) return true
  return false
}

export function hasNavScopeContent(scope) {
  if (!scope || typeof scope !== 'object') return false
  if (cleanStrList(scope.selected_student_ids).length) return true
  if (cleanStrList(scope.classes).length) return true
  if (cleanStrList(scope.majors).length) return true
  const week = scope.week_range
  if (Array.isArray(week) && week.length >= 2 && week[0] != null && week[1] != null) {
    return true
  }
  return false
}

export function hasScopeContent(scope) {
  if (!scope || typeof scope !== 'object') return false
  if (hasNavScopeContent(scope)) return true
  if (cleanStrList(scope.knowledge_ids).length) return true
  if (cleanStrList(scope.title_ids).length) return true
  if (scope.dataset?.run_id || scope.dataset?.dataset_id) return true
  if (scope.view_snapshot?.view) return true
  if (scope.report?.path) return true
  return false
}

export function formatScopeAttachmentMeta(scope, ui = {}) {
  if (!scope) return ''
  const parts = []
  const ids = cleanStrList(scope.selected_student_ids)
  if (ids.length) {
    const labelFn = ui.scopeAttachStudents || ((n) => `已选 ${n} 人`)
    parts.push(labelFn(ids.length))
  }
  const week = scope.week_range
  if (Array.isArray(week) && week.length >= 2 && week[0] != null && week[1] != null) {
    parts.push(`第 ${week[0]}–${week[1]} 周`)
  }
  const classes = cleanStrList(scope.classes)
  if (classes.length) {
    parts.push(classes.slice(0, 2).join('、') + (classes.length > 2 ? '…' : ''))
  }
  const majors = cleanStrList(scope.majors)
  if (majors.length) {
    parts.push(majors.slice(0, 2).join('、') + (majors.length > 2 ? '…' : ''))
  }
  const knowledges = cleanStrList(scope.knowledge_ids)
  if (knowledges.length) {
    parts.push(`知识点 ${knowledges.length}`)
  }
  const titles = cleanStrList(scope.title_ids)
  if (titles.length) {
    parts.push(`题目 ${titles.length}`)
  }
  if (scope.dataset?.label || scope.dataset?.run_id) {
    parts.push(scope.dataset.label || '上次查询')
  }
  if (scope.view_snapshot?.view) {
    parts.push(scope.view_snapshot.label || scope.view_snapshot.view)
  }
  if (scope.report?.path) {
    parts.push(scope.report.label || scope.report.path.split('/').pop())
  }
  return parts.join(' · ') || (ui.scopeAttachEmpty || '当前范围')
}

function cloneDataset(dataset) {
  if (!dataset || typeof dataset !== 'object') return null
  const runId = String(dataset.run_id || '').trim()
  const datasetId = String(dataset.dataset_id || '').trim()
  if (!runId && !datasetId) return null
  return {
    run_id: runId || undefined,
    dataset_id: datasetId || undefined,
    label: String(dataset.label || '').trim() || undefined,
    tool: String(dataset.tool || '').trim() || undefined,
    resource: String(dataset.resource || '').trim() || undefined,
  }
}

function cloneViewSnapshot(snap) {
  if (!snap || typeof snap !== 'object' || !snap.view) return null
  return {
    view: String(snap.view),
    params: snap.params && typeof snap.params === 'object' ? { ...snap.params } : {},
    label: String(snap.label || '').trim() || undefined,
  }
}

function cloneReport(report) {
  if (!report || typeof report !== 'object') return null
  const path = String(report.path || '').trim()
  if (!path) return null
  return {
    path,
    label: String(report.label || '').trim() || path.split('/').pop(),
  }
}

export function cloneScopeAttachment(scope) {
  if (!scope || typeof scope !== 'object') return null
  const out = {
    selected_student_ids: cleanStrList(scope.selected_student_ids),
  }
  const classes = cleanStrList(scope.classes)
  if (classes.length) out.classes = classes
  const majors = cleanStrList(scope.majors)
  if (majors.length) out.majors = majors
  if (Array.isArray(scope.week_range) && scope.week_range.length >= 2) {
    out.week_range = [scope.week_range[0], scope.week_range[1]]
  }
  const knowledgeIds = cleanStrList(scope.knowledge_ids)
  if (knowledgeIds.length) out.knowledge_ids = knowledgeIds
  const titleIds = cleanStrList(scope.title_ids)
  if (titleIds.length) out.title_ids = titleIds
  const dataset = cloneDataset(scope.dataset)
  if (dataset) out.dataset = dataset
  const view = cloneViewSnapshot(scope.view_snapshot)
  if (view) out.view_snapshot = view
  const report = cloneReport(scope.report)
  if (report) out.report = report
  return hasScopeContent(out) ? out : null
}

export function buildScopeAttachmentFromContext(context) {
  if (!context || typeof context !== 'object') return null
  const out = {
    selected_student_ids: cleanStrList(context.selected_student_ids),
  }
  const classes = cleanStrList(context.classes)
  if (classes.length) out.classes = classes
  const majors = cleanStrList(context.majors)
  if (majors.length) out.majors = majors
  if (Array.isArray(context.week_range) && context.week_range.length >= 2) {
    out.week_range = [context.week_range[0], context.week_range[1]]
  }
  const knowledgeIds = cleanStrList(context.knowledge_ids)
  if (knowledgeIds.length) out.knowledge_ids = knowledgeIds
  const titleIds = cleanStrList(context.title_ids)
  if (titleIds.length) out.title_ids = titleIds
  const dataset = cloneDataset(context.dataset)
  if (dataset) out.dataset = dataset
  const view = cloneViewSnapshot(context.view_snapshot)
  if (view) out.view_snapshot = view
  const report = cloneReport(context.report)
  if (report) out.report = report
  return hasScopeContent(out) ? out : null
}

/** Key for nav-driven auto-reset (extras are manual and ignored). */
export function scopeAttachmentNavKey(scope) {
  if (!scope) return ''
  const ids = (scope.selected_student_ids || []).join(',')
  const week = Array.isArray(scope.week_range) ? scope.week_range.join('-') : ''
  const classes = (scope.classes || []).join(',')
  const majors = (scope.majors || []).join(',')
  return `${ids}|${week}|${classes}|${majors}`
}

export function scopeAttachmentKey(scope) {
  if (!scope) return ''
  const nav = scopeAttachmentNavKey(scope)
  const knowledge = (scope.knowledge_ids || []).join(',')
  const titles = (scope.title_ids || []).join(',')
  const dataset = scope.dataset?.run_id || scope.dataset?.dataset_id || ''
  const view = scope.view_snapshot?.view || ''
  const report = scope.report?.path || ''
  return `${nav}|${knowledge}|${titles}|${dataset}|${view}|${report}`
}

export function buildDatasetAttachmentFromStep(step) {
  if (!step?.run_id) return null
  const tool = String(step.tool || '').trim()
  const resource = String(step.resource || '').trim()
  const labelParts = []
  if (tool) labelParts.push(tool)
  if (resource) labelParts.push(resource)
  return {
    run_id: String(step.run_id),
    dataset_id: step.dataset_id ? String(step.dataset_id) : undefined,
    label: labelParts.length ? `基于 ${labelParts.join(' · ')}` : '基于上次查询',
    tool: tool || undefined,
    resource: resource || undefined,
  }
}

export function buildViewSnapshotAttachment({ view, params, label } = {}) {
  if (!view) return null
  return {
    view: String(view),
    params: params && typeof params === 'object' ? { ...params } : {},
    label: label || `当前 ${view}`,
  }
}

export function buildReportAttachment(link) {
  if (!link?.path) return null
  const path = String(link.path)
  return {
    path,
    label: link.label || path.split('/').pop() || path,
  }
}

export const VIEW_FRIENDLY_NAMES = {
  QuestionView: '题目视图',
  WeekView: '周趋势视图',
  StudentView: '学生列表',
  ScatterView: '散点视图',
  PortraitView: '画像视图',
}

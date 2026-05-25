/** 图表跳转：从 tool 结果解析、从正文中剥离 LLM 手写的「可点击入口」段落 */

const VIEW_NAMES = new Set([
  'QuestionView',
  'WeekView',
  'StudentView',
  'ScatterView',
  'PortraitView',
])

/**
 * 去掉 answer 里 LLM 手写的可点击入口列表（与底部结构化按钮重复）
 */
export function stripVisualLinkMarkdown(answer, shouldStrip = true) {
  if (!shouldStrip || !answer) return answer || ''
  let text = String(answer)
  text = text.replace(/\r\n/g, '\n')
  text = text.replace(
    /\n#{1,3}\s*可点击入口\s*\n[\s\S]*?(?=\n#{1,3}\s|\n---\s*\n|$)/gi,
    '\n',
  )
  text = text.replace(/\n[^\n]*(?:这些链接|如下链接)[^\n]*(?:深入|跳转|查看)[^\n]*\n?/gi, '\n')
  return text.replace(/\n{3,}/g, '\n\n').trimEnd()
}

function linkKey(link) {
  try {
    return JSON.stringify({ view: link.view, params: link.params || {} })
  } catch {
    return String(link.view)
  }
}

/** 合并 Agent 误推的多条 WeekView(kind 1/2/3) 为一条 */
export function consolidateWeekViewLinks(links) {
  const list = links || []
  const week = list.filter((l) => l && l.view === 'WeekView')
  const other = list.filter((l) => l && l.view !== 'WeekView')
  if (week.length <= 1) return list

  const kinds = new Set(
    week.map((l) => l.params?.kind).filter((k) => k != null).map((k) => Number(k)),
  )
  if (kinds.size === 1) {
    const k = [...kinds][0]
    return [
      ...other,
      {
        view: 'WeekView',
        params: { kind: k },
        label: `查看周趋势（簇 ${k - 1}）`,
      },
    ]
  }
  return [...other, { view: 'WeekView', params: {}, label: '查看周趋势' }]
}

export function mergeVisualLinks(primary, extra) {
  const out = []
  const seen = new Set()
  for (const list of [primary, extra]) {
    for (const link of list || []) {
      if (!link || !link.view) continue
      const key = linkKey(link)
      if (seen.has(key)) continue
      seen.add(key)
      out.push({
        view: link.view,
        params: link.params || {},
        ...(link.label ? { label: link.label } : {}),
      })
    }
  }
  return consolidateWeekViewLinks(out)
}

/**
 * 从 build_visual_links 的 tool 消息 content 解析 visual_links[]
 */
export function extractVisualLinksFromToolMessages(toolMessages) {
  const links = []
  const seen = new Set()
  for (const msg of toolMessages || []) {
    const name = msg.name || msg.tool
    if (name !== 'build_visual_links') continue
    let payload
    try {
      payload = JSON.parse(msg.content || '{}')
    } catch {
      continue
    }
    for (const link of payload.visual_links || []) {
      if (!link || !link.view) continue
      const key = linkKey(link)
      if (seen.has(key)) continue
      seen.add(key)
      links.push({
        view: link.view,
        params: link.params || {},
        ...(link.label ? { label: link.label } : {}),
      })
    }
  }
  return consolidateWeekViewLinks(links)
}

/** 解析 markdown 内 view 名链接（兜底） */
export function findVisualLinkFromMarkdownClick(href, visualLinks) {
  if (!href || !visualLinks?.length) return null
  const raw = decodeURIComponent(String(href).trim())
  if (VIEW_NAMES.has(raw)) {
    return visualLinks.find((l) => l.view === raw) || { view: raw, params: {} }
  }
  try {
    const u = new URL(raw, 'http://local')
    const view = u.searchParams.get('view')
    if (view && VIEW_NAMES.has(view)) {
      const params = {}
      u.searchParams.forEach((v, k) => {
        if (k !== 'view') params[k] = v
      })
      return visualLinks.find((l) => l.view === view) || { view, params }
    }
  } catch {
    /* ignore */
  }
  return null
}

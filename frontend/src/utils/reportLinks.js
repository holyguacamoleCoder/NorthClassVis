/** Agent 写入 reports/、exports/ 的交付物链接（预览 / 导出） */

const REPORT_PATH_RE = /^(?:reports|exports)\//i

export function isReportDeliverablePath(path) {
  if (!path) return false
  const raw = decodeURIComponent(String(path).trim())
  const normalized = raw.replace(/^\/+/, '').replace(/^data\//i, '')
  return REPORT_PATH_RE.test(normalized)
}

export function normalizeReportPath(href) {
  if (!href) return ''
  let raw = decodeURIComponent(String(href).trim())
  try {
    if (/^https?:\/\//i.test(raw)) {
      const u = new URL(raw)
      raw = u.pathname
    }
  } catch {
    /* ignore */
  }
  raw = raw.replace(/^\/+/, '')
  raw = raw.replace(/^api\/agent\/deliverables\//i, '')
  raw = raw.replace(/\/download\/?$/i, '')
  raw = raw.replace(/^data\//i, '')
  return raw
}

export function findReportLinkFromMarkdownClick(href, reportLinks) {
  const path = normalizeReportPath(href)
  if (!path || !isReportDeliverablePath(path)) return null
  const list = reportLinks || []
  const hit = list.find((l) => l.path === path)
  if (hit) return hit
  const name = path.split('/').pop() || path
  return { path, label: name }
}

/**
 * 去掉 answer 里 LLM 手写的无效报告链接（由底部按钮接管）
 */
export function stripReportLinkMarkdown(answer, shouldStrip = true) {
  if (!shouldStrip || !answer) return answer || ''
  let text = String(answer)
  text = text.replace(/\r\n/g, '\n')
  text = text.replace(
    /\n#{1,3}\s*点击入口\s*\n[\s\S]*?(?=\n#{1,3}\s|\n---\s*\n|$)/gi,
    '\n',
  )
  text = text.replace(
    /\[([^\]]+)\]\((?:https?:\/\/[^/]+)?\/?(?:reports|exports)\/[^)]+\)/gi,
    '',
  )
  text = text.replace(
    /\[([^\]]+)\]\(#\)/g,
    (_, label) => (/\b(report|报告|WeekView|分析)\b/i.test(label) ? '' : `[${label}](#)`),
  )
  text = text.replace(
    /[^\n]*(?:如下链接|以下链接|访问链接|打开链接)[^\n]*(?:报告|文件)[^\n]*\n?/gi,
    '\n',
  )
  return text.replace(/\n{3,}/g, '\n\n').trimEnd()
}

export function extractReportLinksFromToolMessages(toolMessages) {
  const links = []
  const seen = new Set()
  const okRe = /\[(?:Write|Edit)\s+OK:\s*path=([^,\]]+)/i
  for (const msg of toolMessages || []) {
    const name = msg.name || msg.tool
    if (name !== 'write_file' && name !== 'edit_file') continue
    const content = String(msg.content || '')
    if (/^Error/i.test(content.trim())) continue
    let path = ''
    const m = content.match(okRe)
    if (m) path = normalizeReportPath(m[1])
    if (!path && msg.params?.path) path = normalizeReportPath(msg.params.path)
    if (!path || !isReportDeliverablePath(path) || seen.has(path)) continue
    seen.add(path)
    const filename = path.split('/').pop() || path
    const label = filename.replace(/\.(md|txt)$/i, '').replace(/[_-]+/g, ' ')
    links.push({ path, label: label || filename })
  }
  return links
}

export function mergeReportLinks(primary, extra) {
  const out = []
  const seen = new Set()
  for (const list of [primary, extra]) {
    for (const link of list || []) {
      if (!link?.path || seen.has(link.path)) continue
      seen.add(link.path)
      out.push({
        path: link.path,
        label: link.label || link.path.split('/').pop(),
      })
    }
  }
  return out
}

import { renderMarkdown } from '@/utils/markdown.js'
import { splitReportMarkdown, REPORT_CHART_LABELS } from '@/utils/reportCharts.js'

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

function escapeHtml(text) {
  return String(text || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

function chartLabel(view) {
  return REPORT_CHART_LABELS[view] || view || '图表'
}

function serializeSvg(svgEl) {
  if (!svgEl) return ''
  try {
    const clone = svgEl.cloneNode(true)
    clone.setAttribute('xmlns', 'http://www.w3.org/2000/svg')
    return new XMLSerializer().serializeToString(clone)
  } catch {
    return ''
  }
}

/**
 * 从已渲染的 AgentReportBody 根节点收集图表 SVG（与 split 顺序一致）
 */
export function collectChartSnapshots(reportRoot) {
  if (!reportRoot) return []
  const embeds = reportRoot.querySelectorAll('.report-chart-embed')
  return Array.from(embeds).map((embed) => {
    const view = embed.querySelector('.report-chart-embed-title')?.textContent?.trim() || ''
    const svg = embed.querySelector('svg')
    const hint = embed.querySelector('.report-chart-embed-hint')?.textContent?.trim() || ''
    return {
      title: view,
      hint,
      svgHtml: serializeSvg(svg),
      hasChart: !!svg,
    }
  })
}

export function buildReportHtmlDocument({ title, path, segments, snapshots }) {
  const parts = []
  let chartIdx = 0
  for (const seg of segments) {
    if (seg.type === 'md' && seg.content.trim()) {
      parts.push(`<section class="md">${renderMarkdown(seg.content)}</section>`)
      continue
    }
    if (seg.type !== 'chart') continue
    const snap = snapshots[chartIdx++] || {}
    const label = snap.title || chartLabel(seg.view)
    const paramsNote = snap.hint || ''
    if (snap.svgHtml) {
      parts.push(
        `<figure class="report-chart">` +
          `<figcaption><strong>${escapeHtml(label)}</strong>` +
          (paramsNote ? ` <span class="hint">${escapeHtml(paramsNote)}</span>` : '') +
          `</figcaption>` +
          `<div class="chart-svg">${snap.svgHtml}</div>` +
        `</figure>`,
      )
    } else {
      const raw = JSON.stringify({ view: seg.view, params: seg.params || {} })
      parts.push(
        `<figure class="report-chart report-chart--missing">` +
          `<figcaption>${escapeHtml(label)}（导出时未能捕获图表，请在系统内打开预览）</figcaption>` +
          `<pre>${escapeHtml(raw)}</pre>` +
        `</figure>`,
      )
    }
  }

  const body = parts.join('\n')
  return `<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>${escapeHtml(title || '学业报告')}</title>
  <style>
    body { font-family: "Segoe UI", "Microsoft YaHei", sans-serif; line-height: 1.65; color: #222; max-width: 960px; margin: 24px auto; padding: 0 16px; }
    h1,h2,h3 { line-height: 1.35; }
    table { border-collapse: collapse; width: 100%; margin: 12px 0; font-size: 14px; }
    th, td { border: 1px solid #ddd; padding: 6px 10px; text-align: left; }
    th { background: #f0f0f0; }
    pre { background: #f5f5f5; padding: 10px; overflow-x: auto; font-size: 12px; }
    .meta { color: #666; font-size: 12px; margin-bottom: 20px; }
    .report-chart { margin: 20px 0; padding: 12px; border: 1px solid #e0e0e0; border-radius: 8px; background: #fafafa; }
    .report-chart figcaption { margin-bottom: 10px; font-size: 14px; }
    .report-chart .hint { color: #666; font-weight: normal; }
    .chart-svg { overflow-x: auto; }
    .chart-svg svg { max-width: 100%; height: auto; }
    .report-chart--missing pre { margin: 0; }
  </style>
</head>
<body>
  <h1>${escapeHtml(title || '学业报告')}</h1>
  ${path ? `<p class="meta">${escapeHtml(path)}</p>` : ''}
  ${body}
  <p class="meta">由 NorthClassVision 导出 · 图表与仪表盘面板同源</p>
</body>
</html>`
}

export function downloadHtmlReport(html, filename) {
  const blob = new Blob([html], { type: 'text/html;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename || 'report.html'
  a.click()
  URL.revokeObjectURL(url)
}

/**
 * 等待预览内图表渲染后导出 HTML（内嵌 SVG，非 JSON 代码块）
 */
export async function exportReportHtmlFromPreview({
  title,
  path,
  content,
  reportRoot,
  waitMs = 2200,
}) {
  await sleep(waitMs)
  const segments = splitReportMarkdown(content)
  const snapshots = collectChartSnapshots(reportRoot)
  const html = buildReportHtmlDocument({ title, path, segments, snapshots })
  const base = (title || 'report').replace(/[^\w\u4e00-\u9fa5-]+/g, '_').slice(0, 48)
  downloadHtmlReport(html, `${base || 'report'}.html`)
}

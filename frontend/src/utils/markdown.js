import { marked } from 'marked'
import { isChartPayloadText } from '@/utils/reportCharts.js'

marked.setOptions({
  breaks: true,
  gfm: true,
})

marked.use({
  renderer: {
    code({ text, lang }) {
      if (lang === 'mermaid') {
        return `<div class="mermaid">${text}</div>\n`
      }
      if (
        lang === 'report-chart' ||
        lang === 'chart' ||
        (lang === 'json' && isChartPayloadText(text)) ||
        (!lang && isChartPayloadText(text))
      ) {
        return '<p class="report-chart-md-hint">📊 图表请在报告预览中查看（上方预览窗口会渲染交互图表）</p>\n'
      }
      const langClass = lang ? ` class="language-${lang}"` : ''
      const escaped = text
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
      return `<pre><code${langClass}>${escaped}</code></pre>\n`
    },
  },
})

export function renderMarkdown(source) {
  const text = String(source || '').trim()
  if (!text) return ''
  return marked.parse(text)
}

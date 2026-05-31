<template>
  <div class="agent-markdown" v-html="html" @click="onClick"></div>
</template>

<script>
import { renderMarkdown } from '@/utils/markdown.js'
import {
  findReportLinkFromMarkdownClick,
  isReportDeliverablePath,
  normalizeReportPath,
} from '@/utils/reportLinks.js'

export default {
  name: 'AgentMarkdown',
  props: {
    source: { type: String, default: '' },
  },
  emits: ['link-click', 'report-link-click'],
  computed: {
    html() {
      return renderMarkdown(this.source)
    },
  },
  methods: {
    onClick(e) {
      const anchor = e.target.closest('a')
      if (!anchor) return
      const href = anchor.getAttribute('href')
      if (!href || href === '#') {
        e.preventDefault()
        this.$emit('link-click', anchor.textContent || '')
        return
      }
      const reportPath = normalizeReportPath(href)
      if (
        isReportDeliverablePath(reportPath) ||
        isReportDeliverablePath(href)
      ) {
        e.preventDefault()
        const link = findReportLinkFromMarkdownClick(href, []) || {
          path: reportPath,
          label: anchor.textContent?.trim() || reportPath,
        }
        this.$emit('report-link-click', link)
        return
      }
      if (/View$/.test(href) || href.includes('view=')) {
        e.preventDefault()
        this.$emit('link-click', href)
      }
    },
  },
}
</script>

<style scoped lang="less">
.agent-markdown {
  font-size: 15px;
  line-height: 1.65;
  color: #222;
  word-break: break-word;

  :deep(h1),
  :deep(h2),
  :deep(h3),
  :deep(h4) {
    margin: 14px 0 8px;
    font-weight: 700;
    line-height: 1.35;
  }
  :deep(h1) {
    font-size: 1.35em;
  }
  :deep(h2) {
    font-size: 1.2em;
  }
  :deep(h3) {
    font-size: 1.08em;
  }
  :deep(p) {
    margin: 8px 0;
  }
  :deep(ul),
  :deep(ol) {
    margin: 8px 0;
    padding-left: 22px;
  }
  :deep(li) {
    margin: 4px 0;
  }
  :deep(a) {
    color: #377eb8;
    text-decoration: underline;
    cursor: pointer;
  }
  :deep(code) {
    background: rgba(0, 0, 0, 0.06);
    padding: 1px 5px;
    border-radius: 4px;
    font-size: 0.92em;
  }
  :deep(pre) {
    background: #1e1e1e;
    color: #eee;
    padding: 12px;
    border-radius: 6px;
    overflow-x: auto;
    margin: 10px 0;
    code {
      background: none;
      padding: 0;
      color: inherit;
    }
  }
  :deep(table) {
    border-collapse: collapse;
    width: 100%;
    margin: 10px 0;
    font-size: 14px;
  }
  :deep(th),
  :deep(td) {
    border: 1px solid #ddd;
    padding: 6px 10px;
    text-align: left;
  }
  :deep(th) {
    background: #f0f0f0;
    font-weight: 600;
  }
  :deep(blockquote) {
    margin: 8px 0;
    padding: 6px 12px;
    border-left: 3px solid #ccc;
    color: #555;
  }
  :deep(strong) {
    font-weight: 700;
  }
  :deep(.report-chart-md-hint) {
    margin: 10px 0;
    padding: 10px 12px;
    background: #f0f7ff;
    border-left: 3px solid #377eb8;
    color: #334;
    font-size: 13px;
  }
}
</style>

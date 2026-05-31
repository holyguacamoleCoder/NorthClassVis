<template>
  <div v-if="open" class="agent-report-modal" @click.self="$emit('close')">
    <div class="agent-report-modal-card" role="dialog" aria-modal="true">
      <header class="agent-report-modal-header">
        <h3 class="agent-report-modal-title">{{ title || ui.reportPreviewTitle }}</h3>
        <span v-if="path" class="agent-report-modal-path">{{ path }}</span>
        <button type="button" class="agent-report-modal-close" :title="ui.cancel" @click="$emit('close')">
          &#10005;
        </button>
      </header>
      <div class="agent-report-modal-body">
        <div v-if="loading" class="agent-report-modal-loading">{{ ui.reportLoading }}</div>
        <div v-else-if="error" class="agent-report-modal-error">{{ error }}</div>
        <AgentReportBody
          v-else-if="content"
          ref="reportBodyRef"
          :source="content"
          class="agent-report-modal-md"
          @link-click="$emit('link-click', $event)"
          @report-link-click="$emit('report-link-click', $event)"
        />
        <p v-else class="agent-report-modal-empty">{{ ui.reportEmpty }}</p>
      </div>
      <footer class="agent-report-modal-footer">
        <button type="button" class="agent-report-btn" :disabled="!path || exporting" @click="exportMarkdown">
          {{ ui.reportExportMd }}
        </button>
        <button
          type="button"
          class="agent-report-btn agent-report-btn--primary"
          :disabled="!content || exporting"
          @click="exportHtml"
        >
          {{ exporting ? ui.reportExporting : ui.reportExportHtml }}
        </button>
        <button type="button" class="agent-report-btn" @click="$emit('close')">
          {{ ui.cancel }}
        </button>
      </footer>
    </div>
  </div>
</template>

<script>
import { AGENT_UI } from '@/constants/agentUiText.js'
import AgentReportBody from '@/components/agent/AgentReportBody.vue'
import { deliverableDownloadUrl } from '@/api/agent.js'
import { exportReportHtmlFromPreview } from '@/utils/reportExport.js'

export default {
  name: 'AgentReportPreviewModal',
  components: { AgentReportBody },
  props: {
    open: { type: Boolean, default: false },
    loading: { type: Boolean, default: false },
    title: { type: String, default: '' },
    path: { type: String, default: '' },
    content: { type: String, default: '' },
    error: { type: String, default: '' },
  },
  emits: ['close', 'download', 'link-click', 'report-link-click'],
  data() {
    return { ui: AGENT_UI, exporting: false }
  },
  methods: {
    exportMarkdown() {
      if (!this.path) return
      this.$emit('download')
      window.open(deliverableDownloadUrl(this.path), '_blank')
    },
    async exportHtml() {
      if (!this.content || this.exporting) return
      this.exporting = true
      try {
        const root = this.$refs.reportBodyRef?.$el
        await exportReportHtmlFromPreview({
          title: this.title,
          path: this.path,
          content: this.content,
          reportRoot: root,
        })
      } catch (err) {
        console.error('exportHtml failed', err)
        window.alert(err?.message || 'HTML 导出失败，请稍后重试')
      } finally {
        this.exporting = false
      }
    },
  },
}
</script>

<style scoped lang="less">
.agent-report-modal {
  position: fixed;
  inset: 0;
  z-index: 2000;
  background: rgba(0, 0, 0, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  box-sizing: border-box;
}

.agent-report-modal-card {
  width: min(920px, 100%);
  max-height: min(85vh, 800px);
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.18);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.agent-report-modal-header {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 12px;
  padding: 14px 16px;
  border-bottom: 1px solid #e8ecf0;
  flex-shrink: 0;
}

.agent-report-modal-title {
  margin: 0;
  font-size: 16px;
  font-weight: 700;
  color: #222;
  flex: 1;
  min-width: 120px;
}

.agent-report-modal-path {
  font-size: 11px;
  color: #888;
  font-family: ui-monospace, monospace;
  width: 100%;
}

.agent-report-modal-close {
  border: none;
  background: transparent;
  font-size: 18px;
  color: #666;
  cursor: pointer;
  padding: 4px 8px;
  margin-left: auto;
  &:hover { color: #222; }
}

.agent-report-modal-body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 16px 18px;
}

.agent-report-modal-loading,
.agent-report-modal-error,
.agent-report-modal-empty {
  font-size: 14px;
  color: #666;
  margin: 0;
}

.agent-report-modal-error { color: #721c24; }

.agent-report-modal-md {
  font-size: 14px;
}

.agent-report-modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding: 12px 16px;
  border-top: 1px solid #e8ecf0;
  flex-shrink: 0;
}

.agent-report-btn {
  padding: 8px 14px;
  border: 1px solid #dde3ea;
  border-radius: 8px;
  background: #fff;
  font-size: 13px;
  cursor: pointer;
  &:disabled { opacity: 0.5; cursor: not-allowed; }
  &--primary {
    background: #377eb8;
    border-color: #377eb8;
    color: #fff;
    &:hover { background: #2d6a9f; }
  }
}
</style>

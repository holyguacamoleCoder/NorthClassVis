<template>
  <div v-if="items.length" class="agent-report-evidence">
    <div class="agent-section-label">{{ ui.reportEvidenceSection }}</div>
    <p class="agent-report-evidence-hint">{{ ui.reportEvidenceHint }}</p>
    <ul class="agent-report-evidence-list">
      <li
        v-for="(item, i) in items"
        :key="i"
        class="agent-report-evidence-item"
        :class="itemClass(item)"
      >
        <span class="agent-report-evidence-status">{{ statusLabel(item) }}</span>
        <span class="agent-report-evidence-cite" :title="item.cite">{{ item.cite }}</span>
        <span v-if="item.summary" class="agent-report-evidence-summary">{{ item.summary }}</span>
        <span v-if="metaLine(item)" class="agent-report-evidence-meta">{{ metaLine(item) }}</span>
        <span v-if="item.note" class="agent-report-evidence-note">{{ item.note }}</span>
        <span v-if="item.error" class="agent-report-evidence-error">{{ item.error }}</span>
      </li>
    </ul>
  </div>
</template>

<script>
import { AGENT_UI } from '@/constants/agentUiText.js'

export default {
  name: 'AgentReportEvidence',
  props: {
    items: { type: Array, default: () => [] },
  },
  data() {
    return { ui: AGENT_UI }
  },
  methods: {
    itemClass(item) {
      return item?.verifiable ? 'agent-report-evidence-item--ok' : 'agent-report-evidence-item--fail'
    },
    statusLabel(item) {
      return item?.verifiable ? this.ui.reportEvidenceOk : this.ui.reportEvidenceFail
    },
    metaLine(item) {
      const parts = []
      if (item.resource) parts.push(item.resource)
      if (item.row_count != null) parts.push(`${item.row_count} 行`)
      return parts.join(' · ')
    },
  },
}
</script>

<style scoped lang="less">
.agent-report-evidence {
  margin-top: 10px;
  padding: 8px 10px;
  background: rgba(45, 106, 62, 0.05);
  border-left: 3px solid #2d6a3e;
  border-radius: 4px;
}

.agent-report-evidence-hint {
  margin: 4px 0 8px;
  font-size: 12px;
  color: #666;
  line-height: 1.45;
}

.agent-report-evidence-list {
  margin: 0;
  padding: 0;
  list-style: none;
}

.agent-report-evidence-item {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 6px;
  padding: 6px 0;
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
  font-size: 12px;
  line-height: 1.45;

  &:last-child {
    border-bottom: none;
    padding-bottom: 0;
  }
}

.agent-report-evidence-status {
  flex-shrink: 0;
  padding: 1px 6px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
}

.agent-report-evidence-item--ok .agent-report-evidence-status {
  background: #e8f5e9;
  color: #2d6a3e;
}

.agent-report-evidence-item--fail .agent-report-evidence-status {
  background: #ffebee;
  color: #c62828;
}

.agent-report-evidence-cite {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  color: #333;
  word-break: break-all;
}

.agent-report-evidence-summary {
  color: #555;
}

.agent-report-evidence-meta {
  color: #888;
}

.agent-report-evidence-note {
  color: #e65100;
  flex-basis: 100%;
  font-size: 11px;
}

.agent-report-evidence-error {
  color: #c62828;
  flex-basis: 100%;
}
</style>

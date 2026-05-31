<template>
  <div class="agent-deliverable-links">
    <div class="agent-section-label">{{ ui.reportSection }}</div>
    <div
      v-for="(link, i) in links"
      :key="link.path || i"
      class="agent-deliverable-row"
    >
      <span class="agent-deliverable-name">{{ link.label || link.path }}</span>
      <div class="agent-deliverable-actions">
        <button type="button" class="agent-deliverable-btn" @click="$emit('preview', link)">
          {{ ui.reportPreview }}
        </button>
        <button type="button" class="agent-deliverable-btn agent-deliverable-btn--export" @click="$emit('download', link)">
          {{ ui.reportExport }}
        </button>
      </div>
    </div>
  </div>
</template>

<script>
import { AGENT_UI } from '@/constants/agentUiText.js'

export default {
  name: 'AgentDeliverableLinks',
  props: {
    links: { type: Array, default: () => [] },
  },
  emits: ['preview', 'download'],
  data() {
    return { ui: AGENT_UI }
  },
}
</script>

<style scoped lang="less">
.agent-deliverable-links {
  margin-top: 10px;
}

.agent-deliverable-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 40px;
  gap: 12px;
  margin-top: 8px;
  padding: 10px 12px;
  border: 1px solid #d4e3f0;
  border-radius: 8px;
  background: #f4f9fd;
}

.agent-deliverable-name {
  flex: 1;
  min-width: 0;
  font-size: 14px;
  font-weight: 600;
  color: #1a5a8a;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.agent-deliverable-actions {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}

.agent-deliverable-btn {
  padding: 6px 12px;
  font-size: 13px;
  border: 1px solid #377eb8;
  border-radius: 6px;
  background: #fff;
  color: #377eb8;
  cursor: pointer;
  &:hover { background: #eef4fa; }
  &--export {
    background: #377eb8;
    color: #fff;
    &:hover { background: #2d6a9f; }
  }
}
</style>

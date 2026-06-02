<template>
  <div v-if="items.length" class="agent-memory-saved">
    <div class="agent-section-label">{{ ui.memorySection }}</div>
    <div class="agent-memory-chips">
      <span
        v-for="(item, i) in items"
        :key="i"
        class="agent-memory-chip"
        :title="chipTitle(item)"
      >{{ chipLabel(item) }}</span>
    </div>
  </div>
</template>

<script>
import { AGENT_UI } from '@/constants/agentUiText.js'

export default {
  name: 'AgentMemorySaved',
  props: {
    items: { type: Array, default: () => [] },
  },
  data() {
    return { ui: AGENT_UI }
  },
  methods: {
    chipLabel(item) {
      const label = item?.label || item?.name || item?.target || 'memory'
      const action = item?.action
      if (action && action !== 'saved') {
        return this.ui.memorySavedChip(`${label} (${action})`)
      }
      return this.ui.memorySavedChip(label)
    },
    chipTitle(item) {
      const parts = []
      if (item?.type) parts.push(`type: ${item.type}`)
      if (item?.path) parts.push(item.path)
      return parts.join(' · ') || ''
    },
  },
}
</script>

<style scoped lang="less">
.agent-memory-saved {
  margin-top: 10px;
}

.agent-memory-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 6px;
}

.agent-memory-chip {
  display: inline-block;
  padding: 4px 10px;
  font-size: 12px;
  border-radius: 999px;
  background: #eef6ee;
  color: #2d6a3e;
  border: 1px solid #c8e6c9;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>

<template>
  <div v-if="open" class="agent-memories-modal" @click.self="$emit('close')">
    <div class="agent-memories-modal-card" role="dialog" aria-modal="true" @mousedown.stop>
      <header class="agent-memories-modal-header">
        <h3 class="agent-memories-modal-title">{{ ui.memoryModalTitle }}</h3>
        <button type="button" class="agent-memories-modal-close" :title="ui.cancel" @click="$emit('close')">
          &#10005;
        </button>
      </header>
      <div class="agent-memories-modal-body">
        <AgentMemoriesPanel
          ref="panel"
          :initial-edit-name="initialEditName"
          :initial-create="initialCreate"
          @changed="onPanelChanged"
        />
      </div>
    </div>
  </div>
</template>

<script>
import { AGENT_UI } from '@/constants/agentUiText.js'
import AgentMemoriesPanel from '@/components/agent/AgentMemoriesPanel.vue'

export default {
  name: 'AgentMemoriesModal',
  components: { AgentMemoriesPanel },
  props: {
    open: { type: Boolean, default: false },
    initialEditName: { type: String, default: '' },
    initialCreate: { type: Boolean, default: false },
  },
  emits: ['close', 'changed'],
  data() {
    return { ui: AGENT_UI }
  },
  watch: {
    open(visible) {
      if (visible) {
        this.$nextTick(() => this.applyInitial())
      }
    },
    initialEditName() {
      if (this.open) this.$nextTick(() => this.applyInitial())
    },
    initialCreate() {
      if (this.open) this.$nextTick(() => this.applyInitial())
    },
  },
  methods: {
    applyInitial() {
      const panel = this.$refs.panel
      if (!panel) return
      if (this.initialCreate) {
        panel.startCreate()
        return
      }
      if (this.initialEditName) {
        const row = panel.entries.find(
          (e) => e.name === this.initialEditName || e.key === this.initialEditName,
        )
        if (row) panel.openEdit(row)
        else panel.startCreate()
      }
    },
    onPanelChanged() {
      this.$emit('changed')
    },
    reloadRail() {
      this.$emit('changed')
    },
  },
}
</script>

<style scoped lang="less">
.agent-memories-modal {
  position: fixed;
  inset: 0;
  z-index: 1200;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
  background: rgba(0, 0, 0, 0.35);
}

.agent-memories-modal-card {
  width: min(520px, 100%);
  max-height: min(88vh, 720px);
  display: flex;
  flex-direction: column;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.18);
  overflow: hidden;
}

.agent-memories-modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 16px;
  border-bottom: 1px solid #e8ecef;
  flex-shrink: 0;
}

.agent-memories-modal-title {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: #222;
}

.agent-memories-modal-close {
  border: none;
  background: none;
  font-size: 18px;
  line-height: 1;
  color: #888;
  cursor: pointer;
  padding: 4px 8px;
  &:hover {
    color: #333;
  }
}

.agent-memories-modal-body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 12px 16px 16px;
}
</style>

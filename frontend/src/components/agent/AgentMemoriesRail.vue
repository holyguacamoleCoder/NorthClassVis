<template>
  <div class="agent-memories-rail">
    <p class="agent-memories-rail-hint">{{ ui.memoryRailShortHint }}</p>

    <p v-if="loading" class="agent-memories-rail-muted">{{ ui.memoryLoading }}</p>
    <p v-else-if="!enabledEntries.length" class="agent-memories-rail-muted">
      {{ ui.memoryRailActiveEmpty }}
    </p>

    <ul v-else class="agent-memory-tags">
      <li v-for="row in enabledEntries" :key="row.key">
        <button type="button" class="agent-memory-tag" @click="$emit('edit', row)">
          <span class="agent-memory-tag__type">{{ typeLabel(row.type) }}</span>
          <span class="agent-memory-tag__text">{{ row.description || row.name }}</span>
        </button>
      </li>
    </ul>

    <p v-if="disabledCount > 0" class="agent-memories-rail-foot">
      {{ ui.memoryRailDisabledCount(disabledCount) }}
    </p>
  </div>
</template>

<script>
import { listAgentMemories } from '@/api/agent.js'
import { AGENT_UI } from '@/constants/agentUiText.js'

export default {
  name: 'AgentMemoriesRail',
  emits: ['edit', 'changed'],
  data() {
    return {
      ui: AGENT_UI,
      loading: false,
      entries: [],
    }
  },
  computed: {
    enabledEntries() {
      return (this.entries || []).filter(
        (e) => e.enabled !== false && e.kind !== 'rolling',
      )
    },
    disabledCount() {
      return (this.entries || []).filter(
        (e) => e.enabled === false && e.kind !== 'rolling',
      ).length
    },
  },
  mounted() {
    this.reload()
  },
  methods: {
    typeLabel(type) {
      const map = {
        user: this.ui.memoryTypeUser,
        feedback: this.ui.memoryTypeFeedback,
        project: this.ui.memoryTypeProject,
        reference: this.ui.memoryTypeReference,
      }
      return map[type] || type
    },
    async reload() {
      this.loading = true
      try {
        const data = await listAgentMemories()
        this.entries = data.memories || []
      } catch {
        this.entries = []
      } finally {
        this.loading = false
      }
    },
  },
}
</script>

<style scoped lang="less">
.agent-memories-rail-hint {
  margin: 0 0 8px;
  font-size: 11px;
  line-height: 1.4;
  color: #888;
}

.agent-memories-rail-muted {
  margin: 0;
  font-size: 12px;
  color: #888;
  line-height: 1.45;
}

.agent-memory-tags {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.agent-memory-tag {
  display: block;
  width: 100%;
  box-sizing: border-box;
  padding: 8px 10px;
  border: 1px solid #d4e8d9;
  border-radius: 8px;
  background: #f0f7f1;
  text-align: left;
  cursor: pointer;
  transition: background 0.15s, border-color 0.15s;
  &:hover {
    background: #e5f2e8;
    border-color: #9cc9a8;
  }
}

.agent-memory-tag__type {
  display: block;
  font-size: 10px;
  font-weight: 700;
  color: #2d6a3e;
  letter-spacing: 0.02em;
  margin-bottom: 3px;
}

.agent-memory-tag__text {
  display: block;
  font-size: 12px;
  line-height: 1.4;
  color: #333;
  word-break: break-word;
}

.agent-memories-rail-foot {
  margin: 8px 0 0;
  font-size: 11px;
  color: #999;
  line-height: 1.4;
}
</style>

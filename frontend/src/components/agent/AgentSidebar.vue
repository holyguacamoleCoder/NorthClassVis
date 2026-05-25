<template>
  <aside class="agent-sidebar">
    <div class="agent-sidebar-brand">
      <span class="agent-sidebar-logo">Agent</span>
      <span class="agent-sidebar-sub">{{ ui.sidebarSub }}</span>
    </div>
    <button type="button" class="agent-sidebar-new" @click="$emit('create')">
      + {{ ui.newChat }}
    </button>
    <AgentSessionList
      :sessions="sessions"
      :active-id="activeId"
      :loading="loading"
      @select="$emit('select', $event)"
      @rename="$emit('rename', $event)"
      @delete="$emit('delete', $event)"
    />
    <div v-if="sessions.length" class="agent-sidebar-footer">
      {{ ui.sessionCount(sessions.length) }}
    </div>
  </aside>
</template>

<script>
import AgentSessionList from '@/components/agent/AgentSessionList.vue'
import { AGENT_UI } from '@/constants/agentUiText.js'

export default {
  name: 'AgentSidebar',
  components: { AgentSessionList },
  props: {
    sessions: { type: Array, default: () => [] },
    activeId: { type: String, default: null },
    loading: { type: Boolean, default: false },
  },
  emits: ['create', 'select', 'rename', 'delete'],
  data() {
    return { ui: AGENT_UI }
  },
}
</script>

<style scoped lang="less">
.agent-sidebar {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #f7f8fa;
  border-right: 1px solid #e2e6ec;
  min-width: 0;
}

.agent-sidebar-brand {
  padding: 16px 16px 12px;
  flex-shrink: 0;
}

.agent-sidebar-logo {
  display: block;
  font-size: 18px;
  font-weight: 700;
  color: #222;
}

.agent-sidebar-sub {
  display: block;
  font-size: 12px;
  color: #888;
  margin-top: 2px;
}

.agent-sidebar-new {
  margin: 0 12px 12px;
  padding: 10px 14px;
  border: none;
  border-radius: 8px;
  background: #377eb8;
  color: #fff;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  flex-shrink: 0;
  &:hover { background: #2d6a9f; }
}

.agent-sidebar-footer {
  padding: 10px 16px;
  font-size: 11px;
  color: #aaa;
  border-top: 1px solid #e8ecf0;
  flex-shrink: 0;
}
</style>

<template>
  <aside class="agent-context-rail">
    <section class="agent-rail-section">
      <h3 class="agent-rail-heading">{{ ui.railScope }}</h3>
      <AgentScopeFilter ref="scopeFilter" @open-dashboard="openVisualization" @scope-applied="onScopeApplied" />
    </section>

    <section class="agent-rail-section agent-rail-section--scatter">
      <AgentScatterRail ref="scatterRail" />
    </section>

    <section class="agent-rail-section">
      <h3 class="agent-rail-heading">{{ ui.railMode }}</h3>
      <select :value="permissionMode" class="agent-rail-select" @change="onModeChange">
        <option value="consult">{{ ui.modeConsult }}</option>
        <option value="analyze">{{ ui.modeAnalyze }}</option>
        <option value="produce">{{ ui.modeProduce }}</option>
      </select>
    </section>

    <section v-if="todoItems.length" class="agent-rail-section">
      <h3 class="agent-rail-heading">
        {{ ui.railPlan }}
        <span v-if="planLabel" class="agent-rail-plan-progress">{{ planLabel }}</span>
      </h3>
      <ul class="agent-rail-todos">
        <li
          v-for="(item, i) in todoItems"
          :key="i"
          class="agent-rail-todo"
          :class="'agent-rail-todo--' + (item.status || 'pending')"
        >
          <span class="agent-rail-todo-icon">{{ todoIcon(item.status) }}</span>
          <div class="agent-rail-todo-body">
            <span class="agent-rail-todo-text">{{ item.content || '' }}</span>
            <span
              v-if="item.status === 'in_progress' && item.active_form"
              class="agent-rail-todo-active"
            >{{ item.active_form }}</span>
          </div>
        </li>
      </ul>
    </section>

    <section v-if="loadedSkills.length" class="agent-rail-section">
      <h3 class="agent-rail-heading">{{ ui.railSkills }}</h3>
      <AgentSkillTags :skills="loadedSkills" />
    </section>

    <section class="agent-rail-section agent-rail-section--meta">
      <h3 class="agent-rail-heading">{{ ui.railMeta }}</h3>
      <div class="agent-rail-meta-row">
        <span class="agent-rail-meta-label">{{ ui.railMessageCount }}</span>
        <span>{{ messageCount }}</span>
      </div>
    </section>
  </aside>
</template>

<script>
import { mapActions } from 'vuex'
import { AGENT_UI } from '@/constants/agentUiText.js'
import { planProgressLabel, todoIcon } from '@/utils/agentPlanUtils.js'
import AgentScopeFilter from '@/components/agent/AgentScopeFilter.vue'
import AgentScatterRail from '@/components/agent/AgentScatterRail.vue'
import AgentSkillTags from '@/components/agent/AgentSkillTags.vue'

export default {
  name: 'AgentContextRail',
  components: { AgentScopeFilter, AgentScatterRail, AgentSkillTags },
  props: {
    permissionMode: { type: String, default: 'analyze' },
    todoItems: { type: Array, default: () => [] },
    loadedSkills: { type: Array, default: () => [] },
    messageCount: { type: Number, default: 0 },
  },
  emits: ['update:permissionMode', 'open-dashboard'],
  data() {
    return { ui: AGENT_UI, todoIcon }
  },
  computed: {
    planLabel() {
      return planProgressLabel(this.todoItems)
    },
  },
  methods: {
    ...mapActions(['syncDashboardFromAgentScope']),
    onModeChange(e) {
      this.$emit('update:permissionMode', e.target.value)
    },
    async openVisualization() {
      if (this.$refs.scopeFilter?.applyScope) {
        await this.$refs.scopeFilter.applyScope()
      } else {
        await this.$refs.scatterRail?.reloadScatter?.()
      }
      await this.syncDashboardFromAgentScope()
      this.$emit('open-dashboard')
    },
    async onScopeApplied() {
      await this.$store.dispatch('fetchClusterData')
    },
  },
}
</script>

<style scoped lang="less">
.agent-context-rail {
  flex: 1;
  min-height: 0;
  width: 100%;
  overflow-x: hidden;
  overflow-y: auto;
  overscroll-behavior: contain;
  -webkit-overflow-scrolling: touch;
  padding: 16px 14px 24px;
  box-sizing: border-box;
}

.agent-rail-section {
  margin-bottom: 20px;
  &--scatter {
    margin-bottom: 16px;
  }
  &--meta {
    margin-bottom: 0;
  }
}

.agent-rail-heading {
  font-size: 12px;
  font-weight: 700;
  color: #666;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  margin: 0 0 10px;
}

.agent-rail-plan-progress {
  font-weight: 500;
  color: #888;
  text-transform: none;
  letter-spacing: 0;
  margin-left: 4px;
}

.agent-rail-select {
  width: 100%;
  padding: 8px 10px;
  border: 1px solid #dde3ea;
  border-radius: 8px;
  font-size: 13px;
  background: #fff;
  outline: none;
  &:focus { border-color: #377eb8; }
}

.agent-rail-todos {
  list-style: none;
  margin: 0;
  padding: 0;
}

.agent-rail-todo {
  display: flex;
  gap: 8px;
  align-items: flex-start;
  padding: 6px 0;
  font-size: 13px;
  border-bottom: 1px solid #f0f0f0;
  &:last-child { border-bottom: none; }
  &--completed .agent-rail-todo-text {
    color: #888;
    text-decoration: line-through;
  }
  &--in_progress .agent-rail-todo-text {
    color: #856404;
    font-weight: 500;
  }
}

.agent-rail-todo-icon {
  flex-shrink: 0;
  font-size: 12px;
  width: 16px;
  text-align: center;
}

.agent-rail-todo-body {
  flex: 1;
  min-width: 0;
}

.agent-rail-todo-text {
  line-height: 1.4;
  color: #333;
}

.agent-rail-todo-active {
  display: block;
  margin-top: 2px;
  font-size: 11px;
  color: #856404;
}

.agent-rail-meta-row {
  display: flex;
  justify-content: space-between;
  font-size: 13px;
  color: #555;
}

.agent-rail-meta-label {
  color: #888;
}
</style>

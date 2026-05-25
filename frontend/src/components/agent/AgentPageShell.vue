<template>
  <div class="agent-page-shell">
    <header class="agent-app-bar">
      <div class="agent-app-bar-left">
        <button type="button" class="agent-app-btn" :title="ui.backDashboard" @click="$emit('back')">&larr;</button>
        <button
          type="button"
          class="agent-app-btn agent-app-btn--ghost"
          :title="ui.toggleSidebar"
          @click="$emit('toggle-sidebar')"
        >&#9776;</button>
        <div v-if="!editingTitle" class="agent-app-title-wrap" @click="startEditTitle">
          <span class="agent-app-title">{{ sessionTitle || ui.defaultTitle }}</span>
          <span class="agent-app-title-edit-hint">{{ ui.clickToEditTitle }}</span>
        </div>
        <div v-else class="agent-app-title-edit">
          <input
            ref="titleInput"
            v-model="titleDraft"
            type="text"
            class="agent-app-title-input"
            maxlength="200"
            @keydown.enter.prevent="saveTitle"
            @keydown.esc.prevent="cancelEditTitle"
            @blur="saveTitle"
          />
        </div>
      </div>
      <div class="agent-app-bar-right">
        <button type="button" class="agent-app-btn agent-app-btn--text" @click="$emit('float')">{{ ui.floatMode }}</button>
        <button
          type="button"
          class="agent-app-btn agent-app-btn--ghost"
          :class="{ 'agent-app-btn--rail-active': railOpen }"
          :title="ui.toggleRail"
          @click="$emit('toggle-rail')"
        >
          <span class="agent-rail-toggle-icon" aria-hidden="true">&#9776;</span>
          <span v-if="!isRailInline" class="agent-rail-toggle-label">{{ ui.railScopeShort }}</span>
        </button>
      </div>
    </header>

    <div class="agent-page-body">
      <div
        v-show="sidebarOpen"
        class="agent-page-sidebar-wrap"
        :class="{ 'agent-page-sidebar-wrap--overlay': isNarrow }"
      >
        <slot name="sidebar" />
      </div>
      <main
        class="agent-page-main"
        :class="{ 'agent-page-main--wide-chat': !railOpen || !isRailInline }"
      >
        <slot />
      </main>
      <div v-show="railOpen && isRailInline" class="agent-page-rail-wrap">
        <slot name="rail" />
      </div>
      <div
        v-if="railOpen && !isRailInline"
        class="agent-page-rail-overlay"
        @click.self="$emit('toggle-rail')"
      >
        <div class="agent-page-rail-drawer">
          <slot name="rail" />
        </div>
      </div>
    </div>

    <div
      v-if="sidebarOpen && isNarrow"
      class="agent-page-sidebar-backdrop"
      @click="$emit('toggle-sidebar')"
    />
  </div>
</template>

<script>
import { AGENT_UI } from '@/constants/agentUiText.js'

export default {
  name: 'AgentPageShell',
  props: {
    sessionTitle: { type: String, default: '' },
    sidebarOpen: { type: Boolean, default: true },
    railOpen: { type: Boolean, default: true },
  },
  emits: ['back', 'float', 'toggle-sidebar', 'toggle-rail', 'title-save'],
  data() {
    return {
      ui: AGENT_UI,
      editingTitle: false,
      titleDraft: '',
      isNarrow: false,
      isRailInline: false,
    }
  },
  mounted() {
    this.checkWidth()
    window.addEventListener('resize', this.checkWidth)
  },
  beforeUnmount() {
    window.removeEventListener('resize', this.checkWidth)
  },
  methods: {
    checkWidth() {
      const w = window.innerWidth
      this.isNarrow = w < 1024
      this.isRailInline = w >= 1400
    },
    startEditTitle() {
      this.titleDraft = this.sessionTitle || ''
      this.editingTitle = true
      this.$nextTick(() => {
        const el = this.$refs.titleInput
        if (el) {
          el.focus()
          el.select()
        }
      })
    },
    cancelEditTitle() {
      this.editingTitle = false
      this.titleDraft = ''
    },
    saveTitle() {
      const title = (this.titleDraft || '').trim()
      this.editingTitle = false
      if (title && title !== this.sessionTitle) {
        this.$emit('title-save', title)
      }
    },
  },
}
</script>

<style scoped lang="less">
.agent-page-shell {
  position: fixed;
  inset: 0;
  z-index: 200;
  display: flex;
  flex-direction: column;
  background: #eceff3;
}

.agent-app-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 48px;
  padding: 0 12px 0 8px;
  background: #fff;
  border-bottom: 1px solid #e2e6ec;
  flex-shrink: 0;
}

.agent-app-bar-left,
.agent-app-bar-right {
  display: flex;
  align-items: center;
  gap: 4px;
  min-width: 0;
}

.agent-app-bar-left {
  flex: 1;
}

.agent-app-btn {
  width: 36px;
  height: 36px;
  border: none;
  background: transparent;
  border-radius: 8px;
  cursor: pointer;
  font-size: 16px;
  color: #444;
  flex-shrink: 0;
  &:hover { background: #f0f2f5; }

  &--text {
    width: auto;
    padding: 0 12px;
    font-size: 13px;
  }
  &--ghost {
    width: auto;
    min-width: 36px;
    padding: 0 10px;
    font-size: 14px;
    color: #666;
  }
  &--rail-active {
    background: #e8f2fc;
    color: #377eb8;
  }
}

.agent-rail-toggle-icon {
  font-size: 15px;
  line-height: 1;
}

.agent-rail-toggle-label {
  margin-left: 4px;
  font-size: 12px;
  max-width: 72px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.agent-app-btn--ghost.agent-app-btn--rail-active .agent-rail-toggle-label {
  font-weight: 600;
}

.agent-app-title-wrap {
  display: flex;
  align-items: baseline;
  gap: 8px;
  min-width: 0;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 6px;
  &:hover { background: #f5f6f8; }
}

.agent-app-title {
  font-size: 15px;
  font-weight: 600;
  color: #222;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.agent-app-title-edit-hint {
  font-size: 11px;
  color: #aaa;
  flex-shrink: 0;
  opacity: 0;
  transition: opacity 0.15s;
  .agent-app-title-wrap:hover & { opacity: 1; }
}

.agent-app-title-edit {
  flex: 1;
  max-width: 400px;
}

.agent-app-title-input {
  width: 100%;
  padding: 6px 10px;
  border: 1px solid #377eb8;
  border-radius: 6px;
  font-size: 14px;
  outline: none;
}

.agent-page-body {
  flex: 1;
  display: flex;
  min-height: 0;
  position: relative;
}

.agent-page-sidebar-wrap {
  width: 260px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  min-height: 0;

  &--overlay {
    position: absolute;
    left: 0;
    top: 0;
    bottom: 0;
    z-index: 30;
    box-shadow: 4px 0 24px rgba(0, 0, 0, 0.12);
  }
}

.agent-page-sidebar-backdrop {
  position: absolute;
  inset: 0;
  top: 48px;
  background: rgba(0, 0, 0, 0.25);
  z-index: 25;
}

.agent-page-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  background: #fff;
  min-height: 0;
}

.agent-page-main--wide-chat {
  /* ??????????????????? */
}

.agent-page-rail-wrap {
  width: 360px;
  flex-shrink: 0;
  min-height: 0;
  align-self: stretch;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: #fafbfc;
  border-left: 1px solid #e2e6ec;
}

.agent-page-rail-overlay {
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.25);
  z-index: 30;
  display: flex;
  justify-content: flex-end;
}

.agent-page-rail-drawer {
  width: min(360px, 92vw);
  height: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: #fafbfc;
  box-shadow: -4px 0 24px rgba(0, 0, 0, 0.12);
}
</style>

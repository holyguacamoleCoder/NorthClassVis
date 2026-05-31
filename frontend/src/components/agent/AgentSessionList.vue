<template>
  <div class="agent-session-list">
    <div class="agent-session-list-search">
      <input
        v-model="searchQuery"
        type="search"
        class="agent-session-search-input"
        :placeholder="ui.searchSessions"
        @keydown.stop
      />
    </div>
    <div v-if="loading" class="agent-session-list-empty">{{ ui.sessionsLoading }}</div>
    <div v-else-if="!filteredGroups.length" class="agent-session-list-empty">
      {{ searchQuery ? ui.noSessionMatch : ui.noSessions }}
    </div>
    <div v-else class="agent-session-list-groups">
      <div v-for="group in filteredGroups" :key="group.label" class="agent-session-group">
        <div class="agent-session-group-label">{{ group.label }}</div>
        <div
          v-for="s in group.items"
          :key="s.id"
          class="agent-session-row"
          :class="{ 'agent-session-row--active': s.id === activeId }"
          @click="$emit('select', s.id)"
        >
          <span class="agent-session-row-title">{{ s.title || ui.defaultSessionTitle }}</span>
          <span class="agent-session-row-meta">
            {{ sessionListMeta(s) }}
          </span>
          <div class="agent-session-row-actions" @click.stop>
            <button type="button" class="agent-session-action-btn" :title="ui.rename" @click="startRename(s)">&#9998;</button>
            <button type="button" class="agent-session-action-btn agent-session-action-btn--danger" :title="ui.delete" @click="confirmDelete(s)">&#10005;</button>
          </div>
        </div>
      </div>
    </div>

    <div v-if="renamingId" class="agent-session-rename-overlay" @click.self="cancelRename">
      <div class="agent-session-rename-card">
        <div class="agent-session-rename-title">{{ ui.renameSession }}</div>
        <input
          ref="renameInput"
          v-model="renameValue"
          type="text"
          class="agent-session-rename-input"
          maxlength="200"
          @keydown.enter.prevent="submitRename"
          @keydown.esc.prevent="cancelRename"
        />
        <div class="agent-session-rename-actions">
          <button type="button" class="agent-session-rename-btn" @click="cancelRename">{{ ui.cancel }}</button>
          <button type="button" class="agent-session-rename-btn agent-session-rename-btn--primary" @click="submitRename">{{ ui.save }}</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { groupSessionsByDate, filterSessionsByQuery } from '@/utils/sessionGroups.js'
import { AGENT_UI } from '@/constants/agentUiText.js'

export default {
  name: 'AgentSessionList',
  props: {
    sessions: { type: Array, default: () => [] },
    activeId: { type: String, default: null },
    loading: { type: Boolean, default: false },
  },
  emits: ['select', 'rename', 'delete'],
  data() {
    return {
      ui: AGENT_UI,
      searchQuery: '',
      renamingId: null,
      renameValue: '',
    }
  },
  computed: {
    filteredGroups() {
      const filtered = filterSessionsByQuery(this.sessions, this.searchQuery)
      return groupSessionsByDate(filtered)
    },
  },
  methods: {
    sessionListMeta(session) {
      const messages = Number(session?.message_count) || 0
      const turns = Number(session?.user_turn_count) || 0
      return this.ui.sessionListMeta(messages, turns)
    },
    startRename(session) {
      this.renamingId = session.id
      this.renameValue = session.title || ''
      this.$nextTick(() => {
        const el = this.$refs.renameInput
        if (el) {
          el.focus()
          el.select()
        }
      })
    },
    cancelRename() {
      this.renamingId = null
      this.renameValue = ''
    },
    submitRename() {
      const title = (this.renameValue || '').trim()
      if (!title || !this.renamingId) {
        this.cancelRename()
        return
      }
      this.$emit('rename', { id: this.renamingId, title })
      this.cancelRename()
    },
    confirmDelete(session) {
      if (!session?.id) return
      const title = session.title || this.ui.defaultSessionTitle
      const ok = window.confirm(this.ui.deleteConfirm(title))
      if (ok) this.$emit('delete', session.id)
    },
  },
}
</script>

<style scoped lang="less">
.agent-session-list {
  display: flex;
  flex-direction: column;
  min-height: 0;
  flex: 1;
}

.agent-session-list-search {
  padding: 0 12px 10px;
  flex-shrink: 0;
}

.agent-session-search-input {
  width: 100%;
  box-sizing: border-box;
  padding: 8px 10px;
  border: 1px solid #dde3ea;
  border-radius: 8px;
  font-size: 13px;
  background: #fff;
  outline: none;
  &:focus { border-color: #377eb8; }
}

.agent-session-list-groups {
  flex: 1;
  overflow-y: auto;
  padding: 0 8px 12px;
}

.agent-session-group-label {
  font-size: 11px;
  font-weight: 600;
  color: #888;
  padding: 8px 8px 4px;
  letter-spacing: 0.03em;
}

.agent-session-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  grid-template-rows: auto auto;
  column-gap: 4px;
  row-gap: 2px;
  padding: 8px 10px;
  margin-bottom: 2px;
  border-radius: 8px;
  cursor: pointer;
  border-left: 3px solid transparent;
  transition: background 0.15s;
  &:hover {
    background: rgba(55, 126, 184, 0.08);
    .agent-session-row-actions { opacity: 1; }
  }
  &--active {
    background: rgba(55, 126, 184, 0.12);
    border-left-color: #377eb8;
  }
}

.agent-session-row-title {
  grid-column: 1;
  grid-row: 1;
  font-size: 13px;
  font-weight: 600;
  color: #222;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  min-width: 0;
  line-height: 24px;
}

.agent-session-row-meta {
  grid-column: 1;
  grid-row: 2;
  font-size: 11px;
  color: #888;
  min-width: 0;
}

.agent-session-row-actions {
  grid-column: 2;
  grid-row: 1;
  display: flex;
  gap: 2px;
  align-self: center;
  opacity: 0;
  flex-shrink: 0;
  transition: opacity 0.15s;
}

.agent-session-row--active .agent-session-row-actions { opacity: 1; }

.agent-session-action-btn {
  width: 24px;
  height: 24px;
  border: none;
  background: transparent;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
  color: #666;
  padding: 0;
  line-height: 1;
  &:hover { background: rgba(0, 0, 0, 0.06); }
  &--danger:hover { color: #c0392b; background: #fdecea; }
}

.agent-session-list-empty {
  padding: 24px 16px;
  text-align: center;
  font-size: 13px;
  color: #999;
}

.agent-session-rename-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.35);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 500;
  padding: 16px;
}

.agent-session-rename-card {
  background: #fff;
  border-radius: 10px;
  padding: 16px;
  width: 100%;
  max-width: 360px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.15);
}

.agent-session-rename-title {
  font-weight: 600;
  margin-bottom: 10px;
  font-size: 14px;
}

.agent-session-rename-input {
  width: 100%;
  box-sizing: border-box;
  padding: 10px 12px;
  border: 1px solid #ddd;
  border-radius: 8px;
  font-size: 14px;
  margin-bottom: 12px;
  outline: none;
  &:focus { border-color: #377eb8; }
}

.agent-session-rename-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.agent-session-rename-btn {
  padding: 8px 14px;
  border: 1px solid #ddd;
  border-radius: 6px;
  background: #fff;
  cursor: pointer;
  font-size: 13px;
  &--primary {
    background: #377eb8;
    color: #fff;
    border-color: #377eb8;
  }
}
</style>

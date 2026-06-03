<template>
  <section class="agent-memories-panel">
    <div class="agent-memories-toolbar">
      <div class="agent-memories-actions agent-memories-actions--bar">
        <button
          type="button"
          class="agent-memories-btn agent-memories-btn--primary"
          :disabled="loading || saving"
          @click="startCreate"
        >
          {{ ui.memoryRailNew }}
        </button>
        <button type="button" class="agent-memories-btn" :disabled="loading" @click="reload">
          {{ ui.memoryRailRefresh }}
        </button>
        <button
          v-if="expandedKey || creating"
          type="button"
          class="agent-memories-btn"
          @click="collapse"
        >{{ ui.cancel }}</button>
      </div>
    </div>

    <p class="agent-memories-intro">{{ ui.memoryRailIntro }}</p>

    <!-- 新建 -->
    <div v-if="creating" class="agent-memories-form-card">
      <p class="agent-memories-form-title">{{ ui.memoryRailNew }}</p>
      <MemoryFormFields
        :ui="ui"
        :form="createForm"
        :name-editable="true"
        :type-hint="typeHintFor(createForm.type)"
        @update:form="createForm = $event"
      />
      <div class="agent-memories-editor-actions">
        <button
          type="button"
          class="agent-memories-btn agent-memories-btn--primary"
          :disabled="saving"
          @click="create"
        >{{ ui.memoryCreate }}</button>
      </div>
      <p v-if="error" class="agent-memories-error">{{ error }}</p>
    </div>

    <p v-if="loading" class="agent-memories-hint">{{ ui.memoryLoading }}</p>
    <p v-else-if="!namedEntries.length && !rollingEntries.length && !creating" class="agent-memories-hint">
      {{ ui.memoryRailEmpty }}
    </p>

    <template v-else-if="(namedEntries.length || rollingEntries.length) && !creating">
      <template v-if="namedEntries.length">
        <p class="agent-memories-section-title">{{ ui.memoryRailNamedSection }}</p>
        <p class="agent-memories-list-hint">{{ ui.memoryRailNamedHint }}</p>
        <ul class="agent-memories-list">
          <li
            v-for="row in namedEntries"
            :key="row.key"
            class="agent-memories-item"
            :class="{
              'agent-memories-item--open': expandedKey === row.key,
              'agent-memories-item--disabled': row.enabled === false,
            }"
          >
            <div class="agent-memories-item-row">
              <div class="agent-memories-item-summary">
                <span class="agent-memories-type">{{ typeLabel(row.type) }}</span>
                <span class="agent-memories-name" :title="row.name">{{ row.name }}</span>
                <p v-if="row.description || row.preview" class="agent-memories-preview">
                  {{ row.description || row.preview }}
                </p>
              </div>
              <div class="agent-memories-item-actions">
                <button
                  type="button"
                  class="agent-memories-btn agent-memories-btn--primary"
                  :disabled="saving"
                  @click="openEdit(row)"
                >{{ ui.memoryEdit }}</button>
                <button
                  type="button"
                  class="agent-memories-btn agent-memories-btn--danger"
                  :disabled="saving"
                  @click="remove(row)"
                >{{ ui.delete }}</button>
              </div>
            </div>

            <div v-if="expandedKey === row.key" class="agent-memories-form-card agent-memories-form-card--edit">
              <p class="agent-memories-form-title">{{ ui.memoryEditTitle(row.name) }}</p>
              <MemoryFormFields
                :ui="ui"
                :form="editForm"
                :name-editable="false"
                :readonly-name="row.name"
                :type-hint="typeHintFor(editForm.type)"
                @update:form="editForm = $event"
              />
              <div class="agent-memories-editor-actions">
                <button
                  type="button"
                  class="agent-memories-btn agent-memories-btn--primary"
                  :disabled="saving"
                  @click="save(row)"
                >{{ ui.memorySave }}</button>
                <button type="button" class="agent-memories-btn" :disabled="saving" @click="collapse">
                  {{ ui.cancel }}
                </button>
              </div>
              <p v-if="error" class="agent-memories-error">{{ error }}</p>
            </div>
          </li>
        </ul>
      </template>

      <template v-if="rollingEntries.length">
        <p class="agent-memories-section-title agent-memories-section-title--rolling">
          {{ ui.memoryRailRollingSection }}
        </p>
        <p class="agent-memories-list-hint">{{ ui.memoryRailRollingHint }}</p>
        <ul class="agent-memories-list">
          <li
            v-for="row in rollingEntries"
            :key="row.key"
            class="agent-memories-item agent-memories-item--rolling"
            :class="{
              'agent-memories-item--open': expandedKey === row.key,
              'agent-memories-item--disabled': row.enabled === false,
            }"
          >
            <div class="agent-memories-item-row">
              <div class="agent-memories-item-summary">
                <span class="agent-memories-type">{{ typeLabel(row.type) }}</span>
                <span class="agent-memories-name" :title="row.name">{{ row.name }}</span>
                <p v-if="row.description || row.preview" class="agent-memories-preview">
                  {{ row.description || row.preview }}
                </p>
              </div>
              <div class="agent-memories-item-actions">
                <button
                  type="button"
                  class="agent-memories-btn agent-memories-btn--primary"
                  :disabled="saving"
                  @click="openEdit(row)"
                >{{ ui.memoryEdit }}</button>
                <button
                  type="button"
                  class="agent-memories-btn agent-memories-btn--danger"
                  :disabled="saving"
                  @click="remove(row)"
                >{{ ui.delete }}</button>
              </div>
            </div>

            <div v-if="expandedKey === row.key" class="agent-memories-form-card agent-memories-form-card--edit">
              <p class="agent-memories-form-title">{{ ui.memoryEditTitle(row.name) }}</p>
              <MemoryFormFields
                :ui="ui"
                :form="editForm"
                :name-editable="false"
                :readonly-name="row.name"
                :type-hint="typeHintFor(editForm.type)"
                @update:form="editForm = $event"
              />
              <div class="agent-memories-editor-actions">
                <button
                  type="button"
                  class="agent-memories-btn agent-memories-btn--primary"
                  :disabled="saving"
                  @click="save(row)"
                >{{ ui.memorySave }}</button>
                <button type="button" class="agent-memories-btn" :disabled="saving" @click="collapse">
                  {{ ui.cancel }}
                </button>
              </div>
              <p v-if="error" class="agent-memories-error">{{ error }}</p>
            </div>
          </li>
        </ul>
      </template>
    </template>

    <p v-if="error && !creating && !expandedKey" class="agent-memories-error">{{ error }}</p>
  </section>
</template>

<script>
import {
  listAgentMemories,
  getAgentMemory,
  createAgentMemory,
  updateAgentMemory,
  deleteAgentMemory,
} from '@/api/agent.js'
import { AGENT_UI } from '@/constants/agentUiText.js'
import MemoryFormFields from '@/components/agent/AgentMemoryFormFields.vue'

const EMPTY_CREATE = {
  name: '',
  type: 'user',
  description: '',
  content: '',
  enabled: true,
}

export default {
  name: 'AgentMemoriesPanel',
  components: { MemoryFormFields },
  props: {
    initialEditName: { type: String, default: '' },
    initialCreate: { type: Boolean, default: false },
  },
  data() {
    return {
      ui: AGENT_UI,
      loading: false,
      saving: false,
      creating: false,
      entries: [],
      expandedKey: null,
      editingRow: null,
      createForm: { ...EMPTY_CREATE },
      editForm: { type: 'user', description: '', content: '', enabled: true },
      error: '',
    }
  },
  computed: {
    namedEntries() {
      return (this.entries || []).filter((e) => e.kind !== 'rolling')
    },
    rollingEntries() {
      return (this.entries || []).filter((e) => e.kind === 'rolling')
    },
  },
  mounted() {
    this.reload().then(() => this.applyInitialIntent())
  },
  methods: {
    applyInitialIntent() {
      if (this.initialCreate) {
        this.startCreate()
        return
      }
      if (this.initialEditName) {
        const row = this.entries.find(
          (e) => e.name === this.initialEditName || e.key === this.initialEditName,
        )
        if (row) this.openEdit(row)
      }
    },
    typeLabel(type) {
      const map = {
        user: this.ui.memoryTypeUser,
        feedback: this.ui.memoryTypeFeedback,
        project: this.ui.memoryTypeProject,
        reference: this.ui.memoryTypeReference,
      }
      return map[type] || type
    },
    typeHintFor(type) {
      const map = {
        user: this.ui.memoryTypeUserDesc,
        feedback: this.ui.memoryTypeFeedbackDesc,
        project: this.ui.memoryTypeProjectDesc,
        reference: this.ui.memoryTypeReferenceDesc,
      }
      return map[type] || ''
    },
    async reload() {
      this.loading = true
      this.error = ''
      try {
        const data = await listAgentMemories()
        this.entries = data.memories || []
        if (this.expandedKey && this.editingRow) {
          const still = this.entries.find((e) => e.key === this.expandedKey)
          if (!still) this.collapse()
        }
      } catch (e) {
        this.error = e?.message || '加载失败'
        this.entries = []
      } finally {
        this.loading = false
      }
    },
    collapse() {
      this.expandedKey = null
      this.editingRow = null
      this.creating = false
      this.createForm = { ...EMPTY_CREATE }
      this.error = ''
    },
    startCreate() {
      this.creating = true
      this.expandedKey = null
      this.editingRow = null
      this.createForm = { ...EMPTY_CREATE }
      this.error = ''
    },
    async openEdit(row) {
      if (this.expandedKey === row.key) return
      this.creating = false
      this.error = ''
      this.expandedKey = row.key
      this.editingRow = row
      try {
        const detail = await getAgentMemory(row.name)
        this.editForm = {
          type: detail.type || 'user',
          description: detail.description || '',
          content: detail.content || '',
          enabled: detail.enabled !== false,
        }
      } catch (e) {
        this.error = e?.message || '读取失败'
        this.editForm = {
          type: row.type || 'user',
          description: row.description || '',
          content: row.preview || '',
          enabled: row.enabled !== false,
        }
      }
    },
    async create() {
      const name = (this.createForm.name || '').trim()
      const content = (this.createForm.content || '').trim()
      if (!name) {
        this.error = '请填写标识'
        return
      }
      if (!content) {
        this.error = '请填写要记住的内容'
        return
      }
      this.saving = true
      this.error = ''
      try {
        await createAgentMemory({
          name,
          type: this.createForm.type,
          description: (this.createForm.description || '').trim(),
          content,
          enabled: this.createForm.enabled !== false,
        })
        this.creating = false
        this.createForm = { ...EMPTY_CREATE }
        await this.reload()
        const row = this.entries.find((e) => e.name === name)
        if (row) await this.openEdit(row)
        this.$emit('changed')
      } catch (e) {
        this.error = e?.response?.data?.error || e?.message || '创建失败'
      } finally {
        this.saving = false
      }
    },
    async save(row) {
      const content = (this.editForm.content || '').trim()
      if (!content) {
        this.error = '请填写要记住的内容'
        return
      }
      this.saving = true
      this.error = ''
      try {
        await updateAgentMemory(row.name, {
          type: this.editForm.type,
          description: (this.editForm.description || '').trim(),
          content,
          enabled: this.editForm.enabled !== false,
        })
        await this.reload()
        this.expandedKey = row.key
        this.$emit('changed')
      } catch (e) {
        this.error = e?.response?.data?.error || e?.message || '保存失败'
      } finally {
        this.saving = false
      }
    },
    async remove(row) {
      if (!window.confirm(this.ui.memoryDeleteConfirm(row.name))) return
      this.saving = true
      this.error = ''
      try {
        await deleteAgentMemory(row.name)
        this.collapse()
        await this.reload()
        this.$emit('changed')
      } catch (e) {
        this.error = e?.response?.data?.error || e?.message || '删除失败'
      } finally {
        this.saving = false
      }
    },
  },
}
</script>

<style scoped lang="less">
.agent-memories-panel {
  margin-bottom: 0;
}

.agent-memories-toolbar {
  margin-bottom: 10px;
}

.agent-memories-actions--bar {
  justify-content: flex-start;
}

.agent-memories-item--disabled {
  opacity: 0.55;
  .agent-memories-name {
    color: #888;
  }
}

.agent-memories-intro {
  margin: 0 0 12px;
  padding: 8px 10px;
  font-size: 12px;
  line-height: 1.5;
  color: #555;
  background: #f4f8fb;
  border-radius: 8px;
  border: 1px solid #e3edf5;
}

.agent-memories-list-hint {
  margin: 0 0 8px;
  font-size: 11px;
  color: #888;
}

.agent-memories-section-title {
  margin: 16px 0 6px;
  font-size: 12px;
  font-weight: 700;
  color: #555;
  &:first-of-type {
    margin-top: 0;
  }
  &--rolling {
    color: #666;
    margin-top: 18px;
    padding-top: 14px;
    border-top: 1px solid #eef1f5;
  }
}

.agent-memories-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
  justify-content: flex-end;
}

.agent-memories-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 28px;
  padding: 4px 10px;
  font-size: 12px;
  line-height: 1.25;
  border: 1px solid #dde3ea;
  border-radius: 6px;
  background: #fff;
  cursor: pointer;
  box-sizing: border-box;
  white-space: nowrap;
  &--primary {
    background: #377eb8;
    border-color: #377eb8;
    color: #fff;
  }
  &--danger {
    color: #b33;
    border-color: #e8c4c4;
    background: #fff5f5;
  }
  &:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
}

.agent-memories-hint {
  font-size: 12px;
  color: #888;
  line-height: 1.45;
  margin: 0;
}

.agent-memories-form-card {
  margin-bottom: 12px;
  padding: 12px;
  border: 1px solid #d4e3f0;
  border-radius: 8px;
  background: #f8fbfd;
  &--edit {
    margin-top: 10px;
  }
}

.agent-memories-form-title {
  margin: 0 0 10px;
  font-size: 13px;
  font-weight: 600;
  color: #1a5a8a;
}

.agent-memories-list {
  list-style: none;
  margin: 0;
  padding: 0;
}

.agent-memories-item {
  border-bottom: 1px solid #f0f0f0;
  padding: 10px 0;
  &:last-child {
    border-bottom: none;
  }
}

.agent-memories-item-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
}

.agent-memories-item-summary {
  flex: 1;
  min-width: 0;
}

.agent-memories-item-actions {
  display: flex;
  flex-direction: column;
  gap: 6px;
  flex-shrink: 0;
}

.agent-memories-type {
  display: inline-block;
  font-size: 10px;
  font-weight: 700;
  color: #2d6a3e;
  background: #eef6ee;
  padding: 2px 6px;
  border-radius: 4px;
  margin-bottom: 4px;
}

.agent-memories-name {
  display: block;
  font-size: 13px;
  font-weight: 600;
  color: #333;
  word-break: break-all;
}

.agent-memories-preview {
  margin: 4px 0 0;
  font-size: 12px;
  color: #777;
  line-height: 1.4;
}

.agent-memories-editor-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 4px;
}

.agent-memories-error {
  margin: 8px 0 0;
  font-size: 12px;
  color: #b33;
}
</style>

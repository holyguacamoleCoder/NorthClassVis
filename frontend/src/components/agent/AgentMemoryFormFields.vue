<template>
  <div class="memory-form-fields">
    <div v-if="nameEditable" class="memory-form-field">
      <label class="memory-form-label">{{ ui.memoryFieldName }}</label>
      <p class="memory-form-hint">{{ ui.memoryHintName }}</p>
      <input
        :value="form.name"
        type="text"
        class="memory-form-input"
        :placeholder="ui.memoryNamePlaceholder"
        @input="patch({ name: $event.target.value })"
      />
    </div>
    <div v-else-if="readonlyName" class="memory-form-field">
      <label class="memory-form-label">{{ ui.memoryNameReadonly }}</label>
      <p class="memory-form-hint">{{ ui.memoryHintName }}</p>
      <input :value="readonlyName" type="text" class="memory-form-input memory-form-input--readonly" disabled />
    </div>

    <div class="memory-form-field">
      <label class="memory-form-label">{{ ui.memoryFieldType }}</label>
      <p class="memory-form-hint">{{ ui.memoryHintType }}</p>
      <select
        :value="form.type"
        class="memory-form-select"
        @change="patch({ type: $event.target.value })"
      >
        <option value="user">{{ ui.memoryTypeUser }}</option>
        <option value="feedback">{{ ui.memoryTypeFeedback }}</option>
        <option value="project">{{ ui.memoryTypeProject }}</option>
        <option value="reference">{{ ui.memoryTypeReference }}</option>
      </select>
      <p v-if="typeHint" class="memory-form-type-hint">{{ typeHint }}</p>
    </div>

    <div class="memory-form-field">
      <label class="memory-form-label">{{ ui.memoryFieldDescription }}</label>
      <p class="memory-form-hint">{{ ui.memoryHintDescription }}</p>
      <input
        :value="form.description"
        type="text"
        class="memory-form-input"
        :placeholder="ui.memoryDescriptionPlaceholder"
        @input="patch({ description: $event.target.value })"
      />
    </div>

    <div class="memory-form-field memory-form-field--checkbox">
      <label class="memory-form-checkbox">
        <input
          type="checkbox"
          :checked="form.enabled !== false"
          @change="patch({ enabled: $event.target.checked })"
        />
        <span class="memory-form-label memory-form-label--inline">{{ ui.memoryEnabled }}</span>
      </label>
      <p class="memory-form-hint">{{ ui.memoryEnabledHint }}</p>
    </div>

    <div class="memory-form-field">
      <label class="memory-form-label">{{ ui.memoryFieldContent }}</label>
      <p class="memory-form-hint">{{ ui.memoryHintContent }}</p>
      <textarea
        :value="form.content"
        class="memory-form-textarea"
        rows="6"
        :placeholder="ui.memoryContentPlaceholder"
        @input="patch({ content: $event.target.value })"
      />
    </div>
  </div>
</template>

<script>
export default {
  name: 'AgentMemoryFormFields',
  props: {
    ui: { type: Object, required: true },
    form: { type: Object, required: true },
    nameEditable: { type: Boolean, default: false },
    readonlyName: { type: String, default: '' },
    typeHint: { type: String, default: '' },
  },
  emits: ['update:form'],
  methods: {
    patch(partial) {
      this.$emit('update:form', { ...this.form, ...partial })
    },
  },
}
</script>

<style scoped lang="less">
.memory-form-field {
  margin-bottom: 12px;
  &:last-child {
    margin-bottom: 0;
  }
}

.memory-form-label {
  display: block;
  font-size: 12px;
  font-weight: 600;
  color: #444;
  margin-bottom: 2px;
}

.memory-form-hint {
  margin: 0 0 6px;
  font-size: 11px;
  line-height: 1.45;
  color: #888;
}

.memory-form-type-hint {
  margin: 6px 0 0;
  padding: 6px 8px;
  font-size: 11px;
  line-height: 1.4;
  color: #2d6a3e;
  background: #f0f7f0;
  border-radius: 6px;
}

.memory-form-input,
.memory-form-textarea,
.memory-form-select {
  width: 100%;
  box-sizing: border-box;
  padding: 8px 10px;
  border: 1px solid #dde3ea;
  border-radius: 6px;
  font-size: 13px;
  font-family: inherit;
  background: #fff;
  &--readonly {
    background: #f0f0f0;
    color: #666;
    cursor: not-allowed;
  }
}

.memory-form-textarea {
  resize: vertical;
  min-height: 100px;
}

.memory-form-checkbox {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  input {
    cursor: pointer;
  }
}

.memory-form-label--inline {
  margin: 0;
  font-size: 13px;
}
</style>

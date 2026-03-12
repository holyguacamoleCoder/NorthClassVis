<template>
  <div v-if="visible" class="agent-float-root">
    <!-- 最小化时只显示右下角小入口 -->
    <div
      v-if="minimized"
      class="agent-pill"
      @click="$emit('expand')"
    >
      Agent
    </div>

    <!-- 展开时的完整浮层：支持拖拽移动 + 右下角调整大小 -->
    <div
      v-else
      ref="panel"
      class="agent-panel"
      :style="panelStyle"
    >
      <div
        class="agent-resize-handle"
        @mousedown="startResize"
      ></div>
      <div
        class="agent-panel-header"
        @mousedown="startDrag"
      >
        <span class="agent-panel-title">教师问答 Agent</span>
        <div class="agent-panel-actions">
          <button type="button" class="btn-icon" title="最小化" @click.stop="$emit('minimize')">−</button>
          <button type="button" class="btn-icon" title="关闭" @click.stop="$emit('close')">×</button>
        </div>
      </div>

      <div class="agent-panel-body">
        <div class="agent-messages" ref="messagesEl">
          <div
            v-for="(msg, idx) in messages"
            :key="idx"
            :class="['agent-msg', 'agent-msg--' + msg.role]"
          >
            <template v-if="msg.role === 'user'">
              <div class="agent-msg-bubble agent-msg-bubble--user">{{ msg.text }}</div>
            </template>
            <template v-else>
              <div class="agent-msg-bubble agent-msg-bubble--assistant">
                <div class="agent-answer">{{ msg.answer }}</div>
                <div v-if="msg.evidence && msg.evidence.length" class="agent-evidence">
                  <div class="agent-section-label">依据</div>
                  <div
                    v-for="(e, i) in msg.evidence"
                    :key="i"
                    class="agent-evidence-item"
                  >
                    <span class="agent-evidence-tool">{{ e.tool }}</span>
                    <span class="agent-evidence-summary">{{ e.summary }}</span>
                  </div>
                </div>
                <div v-if="msg.actions && msg.actions.length" class="agent-actions">
                  <div class="agent-section-label">建议</div>
                  <ul>
                    <li v-for="(a, i) in msg.actions" :key="i">{{ a }}</li>
                  </ul>
                </div>
                <div v-if="msg.visual_links && msg.visual_links.length" class="agent-visual-links">
                  <div class="agent-section-label">图表入口</div>
                  <button
                    v-for="(link, i) in msg.visual_links"
                    :key="i"
                    type="button"
                    class="agent-visual-link-btn"
                    @click="onVisualLinkClick(link)"
                  >
                    {{ visualLinkLabel(link) }}
                  </button>
                </div>
              </div>
            </template>
          </div>
          <div v-if="loading" class="agent-msg agent-msg--assistant">
            <div class="agent-msg-bubble agent-msg-bubble--assistant agent-loading">思考中…</div>
          </div>
        </div>

        <!-- 可折叠运行轨迹 -->
        <div class="agent-trace">
          <button
            type="button"
            class="agent-trace-toggle"
            @click="traceOpen = !traceOpen"
          >
            {{ traceOpen ? '收起' : '查看本次调用轨迹' }}
          </button>
          <div v-show="traceOpen" class="agent-trace-content">
            <template v-if="lastTrace && lastTrace.steps && lastTrace.steps.length">
              <div
                v-for="(step, i) in lastTrace.steps"
                :key="i"
                class="agent-trace-step"
              >
                <span class="agent-trace-tool">{{ step.tool }}</span>
                <span v-if="step.params" class="agent-trace-params">{{ JSON.stringify(step.params) }}</span>
                <span v-if="step.summary" class="agent-trace-summary">{{ step.summary }}</span>
              </div>
            </template>
            <div v-else class="agent-trace-empty">暂无轨迹</div>
          </div>
        </div>

        <div class="agent-input-row">
          <input
            v-model="inputText"
            type="text"
            class="agent-input"
            placeholder="输入问题，如：最近两周链表知识点表现如何？"
            @keydown.enter.prevent="send"
          />
          <button type="button" class="agent-send" :disabled="loading" @click="send">发送</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { postAgentQuery } from '@/api/agent.js'

export default {
  name: 'AgentChatFloat',
  props: {
    visible: { type: Boolean, default: false },
    minimized: { type: Boolean, default: false },
    context: {
      type: Object,
      default: () => ({}),
    },
  },
  data() {
    return {
      messages: [],
      inputText: '',
      loading: false,
      traceOpen: false,
      // 拖拽
      useDragPosition: false,
      dragLeft: 0,
      dragTop: 0,
      dragStartX: 0,
      dragStartY: 0,
      panelRect: null,
      // 缩放
      panelWidth: 420,
      panelHeight: 560,
      resizing: false,
      resizeStartX: 0,
      resizeStartY: 0,
      resizeStartW: 0,
      resizeStartH: 0,
    }
  },
  computed: {
    panelStyle() {
      const base = {
        width: this.panelWidth + 'px',
        height: this.panelHeight + 'px',
      }
      if (this.useDragPosition) {
        base.left = this.dragLeft + 'px'
        base.top = this.dragTop + 'px'
        base.right = 'auto'
        base.bottom = 'auto'
      }
      return base
    },
    lastTrace() {
      for (let i = this.messages.length - 1; i >= 0; i--) {
        if (this.messages[i].role === 'assistant' && this.messages[i].trace) {
          return this.messages[i].trace
        }
      }
      return null
    },
  },
  methods: {
    visualLinkLabel(link) {
      const view = link.view || 'View'
      const p = link.params
      const parts = [view]
      if (p && p.knowledge) parts.push(`（${p.knowledge}）`)
      if (p && p.student_ids) parts.push(`（学生）`)
      return parts.join(' ')
    },
    onVisualLinkClick(link) {
      this.$emit('visual-link-click', { view: link.view, params: link.params || {} })
    },
    startDrag(e) {
      if (!this.$refs.panel) return
      this.panelRect = this.$refs.panel.getBoundingClientRect()
      this.useDragPosition = true
      this.dragLeft = this.panelRect.left
      this.dragTop = this.panelRect.top
      this.dragStartX = e.clientX
      this.dragStartY = e.clientY
      document.addEventListener('mousemove', this.onDrag)
      document.addEventListener('mouseup', this.stopDrag)
    },
    onDrag(e) {
      this.dragLeft += e.clientX - this.dragStartX
      this.dragTop += e.clientY - this.dragStartY
      this.dragStartX = e.clientX
      this.dragStartY = e.clientY
    },
    stopDrag() {
      document.removeEventListener('mousemove', this.onDrag)
      document.removeEventListener('mouseup', this.stopDrag)
    },
    startResize(e) {
      e.preventDefault()
      e.stopPropagation()
      this.resizing = true
      this.resizeStartX = e.clientX
      this.resizeStartY = e.clientY
      this.resizeStartW = this.panelWidth
      this.resizeStartH = this.panelHeight
      document.addEventListener('mousemove', this.onResize)
      document.addEventListener('mouseup', this.stopResize)
    },
    onResize(e) {
      const dx = e.clientX - this.resizeStartX
      const dy = e.clientY - this.resizeStartY
      let w = this.resizeStartW + dx
      let h = this.resizeStartH + dy
      const minW = 320
      const minH = 400
      const maxW = 900
      const maxH = 900
      w = Math.min(maxW, Math.max(minW, w))
      h = Math.min(maxH, Math.max(minH, h))
      this.panelWidth = w
      this.panelHeight = h
    },
    stopResize() {
      this.resizing = false
      document.removeEventListener('mousemove', this.onResize)
      document.removeEventListener('mouseup', this.stopResize)
    },
    async send() {
      const text = (this.inputText || '').trim()
      if (!text || this.loading) return
      this.inputText = ''
      this.messages.push({ role: 'user', text })
      this.loading = true
      try {
        const res = await postAgentQuery(text, this.context)
        this.messages.push({
          role: 'assistant',
          answer: res.answer || '',
          evidence: res.evidence || [],
          actions: res.actions || [],
          visual_links: res.visual_links || [],
          trace: res.trace,
        })
        this.traceOpen = !!res.trace
        this.$nextTick(() => {
          const el = this.$refs.messagesEl
          if (el) el.scrollTop = el.scrollHeight
        })
      } catch (err) {
        this.messages.push({
          role: 'assistant',
          answer: '请求失败，请稍后重试。',
          evidence: [],
          actions: [],
          visual_links: [],
          trace: null,
        })
      } finally {
        this.loading = false
      }
    },
  },
}
</script>

<style scoped lang="less">
.agent-float-root {
  position: fixed;
  z-index: 1000;
  pointer-events: none;
  & > * {
    pointer-events: auto;
  }
}

.agent-pill {
  position: fixed;
  right: 24px;
  bottom: 24px;
  padding: 12px 20px;
  background: #2a2a2a;
  color: #fff;
  border-radius: 24px;
  font-weight: 600;
  font-size: 16px;
  cursor: pointer;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.2);
  &:hover {
    background: #333;
  }
}

.agent-panel {
  position: fixed;
  right: 24px;
  bottom: 24px;
  min-width: 320px;
  min-height: 400px;
  max-width: 900px;
  max-height: 900px;
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.15);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.agent-resize-handle {
  position: absolute;
  right: 0;
  bottom: 0;
  width: 20px;
  height: 20px;
  cursor: nwse-resize;
  z-index: 10;
  &::after {
    content: '';
    position: absolute;
    right: 6px;
    bottom: 6px;
    width: 10px;
    height: 10px;
    border-right: 2px solid #999;
    border-bottom: 2px solid #999;
    border-radius: 0 0 4px 0;
  }
  &:hover::after {
    border-color: #333;
  }
}

.agent-panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  background: #2a2a2a;
  color: #fff;
  cursor: move;
  user-select: none;
}

.agent-panel-title {
  font-weight: 600;
  font-size: 17px;
}

.agent-panel-actions {
  display: flex;
  gap: 6px;
}

.btn-icon {
  width: 32px;
  height: 32px;
  border: none;
  background: rgba(255, 255, 255, 0.2);
  color: #fff;
  border-radius: 4px;
  cursor: pointer;
  font-size: 20px;
  line-height: 1;
  padding: 0;
  &:hover {
    background: rgba(255, 255, 255, 0.3);
  }
}

.agent-panel-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.agent-messages {
  flex: 1;
  overflow-y: auto;
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.agent-msg-bubble {
  max-width: 90%;
  padding: 12px 14px;
  border-radius: 10px;
  font-size: 15px;
  line-height: 1.6;
}

.agent-msg-bubble--user {
  align-self: flex-end;
  background: #2a2a2a;
  color: #fff;
}

.agent-msg-bubble--assistant {
  align-self: flex-start;
  background: #f0f0f0;
  color: #333;
}

.agent-answer {
  margin-bottom: 10px;
  font-size: 15px;
}

.agent-section-label {
  font-size: 13px;
  color: #666;
  margin: 10px 0 6px;
  font-weight: 600;
}

.agent-evidence-item {
  display: block;
  font-size: 14px;
  margin: 6px 0;
}

.agent-evidence-tool {
  color: #377eb8;
  margin-right: 8px;
}

.agent-actions ul {
  margin: 0;
  padding-left: 20px;
  font-size: 14px;
  line-height: 1.5;
}

.agent-visual-links {
  margin-top: 10px;
}

.agent-visual-link-btn {
  display: block;
  width: 100%;
  margin-top: 8px;
  padding: 8px 12px;
  text-align: left;
  font-size: 14px;
  border: 1px solid #ccc;
  border-radius: 6px;
  background: #fff;
  cursor: pointer;
  &:hover {
    background: #f5f5f5;
    border-color: #999;
  }
}

.agent-loading {
  color: #666;
  font-size: 15px;
}

.agent-trace {
  border-top: 1px solid #eee;
  padding: 10px 14px;
  background: #fafafa;
}

.agent-trace-toggle {
  width: 100%;
  padding: 8px 0;
  border: none;
  background: none;
  font-size: 14px;
  color: #666;
  cursor: pointer;
  text-align: left;
  &:hover {
    color: #333;
  }
}

.agent-trace-content {
  font-size: 13px;
  color: #666;
  max-height: 140px;
  overflow-y: auto;
  margin-top: 6px;
}

.agent-trace-step {
  display: block;
  padding: 6px 0;
  border-bottom: 1px solid #eee;
  &:last-child {
    border-bottom: none;
  }
}

.agent-trace-tool {
  color: #377eb8;
  margin-right: 8px;
}

.agent-trace-params {
  margin-right: 8px;
  word-break: break-all;
}

.agent-trace-empty {
  color: #999;
  padding: 10px 0;
  font-size: 13px;
}

.agent-input-row {
  display: flex;
  gap: 10px;
  padding: 12px 14px;
  border-top: 1px solid #eee;
  background: #fff;
}

.agent-input {
  flex: 1;
  padding: 10px 14px;
  border: 1px solid #ddd;
  border-radius: 6px;
  font-size: 15px;
  outline: none;
  &:focus {
    border-color: #2a2a2a;
  }
}

.agent-send {
  padding: 10px 18px;
  background: #2a2a2a;
  color: #fff;
  border: none;
  border-radius: 6px;
  font-size: 15px;
  cursor: pointer;
  &:hover:not(:disabled) {
    background: #333;
  }
  &:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
}
</style>

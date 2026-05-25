<template>
  <div class="agent-scatter-rail">
    <div class="agent-scatter-rail-head">
      <span class="agent-scatter-rail-title">{{ ui.railScatter }}</span>
      <div class="agent-scatter-tools">
        <button
          type="button"
          class="agent-scatter-tool-btn agent-scatter-click-btn"
          :class="{ 'agent-scatter-tool-btn--active': interactionMode === 'click' }"
          :title="ui.railClick"
          :disabled="showLoading"
          @click="toggleClick"
        >
          <span class="agent-scatter-click-icon" />
        </button>
        <button
          type="button"
          class="agent-scatter-tool-btn agent-scatter-brush-btn"
          :class="{ 'agent-scatter-tool-btn--active': interactionMode === 'brush' }"
          :title="ui.railBrush"
          :disabled="showLoading"
          @click="toggleBrush"
        >
          <span class="agent-scatter-brush-icon" />
        </button>
      </div>
    </div>
    <div class="agent-scatter-legend">
      <span v-for="(color, i) in getColors" :key="i" class="agent-scatter-legend-item">
        <i class="agent-scatter-dot" :style="{ background: color }" />簇 {{ i }}
      </span>
    </div>
    <p class="agent-scatter-hint">{{ interactionHint }}</p>
    <div class="agent-scatter-chart-wrap">
      <LoadingSpinner v-if="showLoading" />
      <ScatterView
        ref="scatter"
        container-id="agent-scatter-viz"
        compact
        hide-chrome
        hide-loading-overlay
        @loading-change="onScatterLoadingChange"
      />
    </div>
  </div>
</template>

<script>
import { mapGetters, mapState } from 'vuex'
import ScatterView from '@/components/ScatterView.vue'
import LoadingSpinner from '@/components/LoadingSpinner.vue'
import { AGENT_UI } from '@/constants/agentUiText.js'

export default {
  name: 'AgentScatterRail',
  components: { ScatterView, LoadingSpinner },
  data() {
    return {
      ui: AGENT_UI,
      scatterLoading: false,
      interactionMode: 'click',
    }
  },
  computed: {
    ...mapGetters(['getColors']),
    ...mapState(['navScopeApplying']),
    showLoading() {
      return this.navScopeApplying || this.scatterLoading
    },
    interactionHint() {
      return this.interactionMode === 'brush'
        ? '框选 / 输入学号：拖拽矩形或上方输入框指定学生'
        : '点选 / 输入学号：点击圆点或上方输入框指定学生'
    },
  },
  methods: {
    syncInteractionMode() {
      const scatter = this.$refs.scatter
      if (!scatter) return
      this.interactionMode = scatter.brushEnabled ? 'brush' : 'click'
    },
    toggleBrush() {
      this.$refs.scatter?.toggleBrush?.()
      this.$nextTick(() => this.syncInteractionMode())
    },
    toggleClick() {
      this.$refs.scatter?.toggleClick?.()
      this.$nextTick(() => this.syncInteractionMode())
    },
    onScatterLoadingChange(loading) {
      this.scatterLoading = loading
      if (!loading) {
        this.$store.commit('setNavScopeApplying', false)
        this.syncInteractionMode()
      }
    },
    reloadScatter() {
      return this.$refs.scatter?.loadData?.({ preserveSelection: true })
    },
  },
}
</script>

<style scoped lang="less">
.agent-scatter-rail {
  border-top: 1px solid #eef1f5;
  padding-top: 12px;
}

.agent-scatter-rail-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
}

.agent-scatter-rail-title {
  font-size: 12px;
  font-weight: 700;
  color: #666;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.agent-scatter-tools {
  display: flex;
  gap: 6px;
}

.agent-scatter-tool-btn {
  width: 28px;
  height: 28px;
  border: 1px solid #dde3ea;
  border-radius: 6px;
  background: #fff;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  &:hover:not(:disabled) { background: #f5f8fb; }
  &:disabled {
    opacity: 0.5;
    cursor: wait;
  }
  &--active {
    border-color: #377eb8;
    background: #e8f2fc;
    box-shadow: inset 0 0 0 1px #377eb8;
  }
}

.agent-scatter-brush-icon {
  display: block;
  width: 16px;
  height: 16px;
  background: no-repeat center/85% url('@/assets/images/brush.png');
}

.agent-scatter-click-icon {
  display: block;
  width: 16px;
  height: 16px;
  background: no-repeat center/100% url('@/assets/images/click.png');
}

.agent-scatter-hint {
  margin: 0 0 6px;
  font-size: 11px;
  color: #888;
  line-height: 1.4;
}

.agent-scatter-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 12px;
  margin-bottom: 4px;
  font-size: 11px;
  color: #666;
}

.agent-scatter-legend-item {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.agent-scatter-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  display: inline-block;
}

.agent-scatter-chart-wrap {
  position: relative;
  min-height: 228px;
}

.agent-scatter-chart-wrap :deep(.loading-spinner) {
  height: 100%;
  border-radius: 6px;
}

:deep(#scatter-chart.scatter-chart--compact) {
  .scatter-chrome { display: none; }
  .scatter-id-picker--compact {
    padding-left: 0;
    padding-right: 0;
  }
  .scatter-viz-wrap--compact .loading-spinner {
    height: 100%;
  }
  .scatter-viz-host {
    margin: 0;
    padding: 0;
    box-shadow: none;
  }
}
</style>

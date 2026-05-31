<template>
  <div class="report-chart-embed">
    <div class="report-chart-embed-head">
      <span class="report-chart-embed-title">{{ title }}</span>
      <span v-if="paramsHint" class="report-chart-embed-hint">{{ paramsHint }}</span>
    </div>
    <div v-if="error" class="report-chart-embed-error">{{ error }}</div>
    <div v-else-if="!supported" class="report-chart-embed-error">
      暂不支持在报告中嵌入 {{ view }}，请使用 WeekView / QuestionView / ScatterView / PortraitView。
    </div>
    <div v-else-if="contextError" class="report-chart-embed-error">{{ contextError }}</div>
    <div v-else-if="!contextReady" class="report-chart-embed-loading">正在加载图表数据…</div>
    <div v-else class="report-chart-embed-body">
      <WeekView
        v-if="view === 'WeekView'"
        :key="mountKey"
        embedded
        :chart-params="params"
        :container-id="containerId"
      />
      <QuestionView
        v-else-if="view === 'QuestionView'"
        :key="mountKey"
        embedded
        :chart-params="params"
        :container-id="containerId"
      />
      <ScatterView
        v-else-if="view === 'ScatterView'"
        :key="mountKey"
        compact
        hide-chrome
        :hide-loading-overlay="false"
        :show-id-picker="false"
        :container-id="containerId"
      />
      <PortraitView
        v-else-if="view === 'PortraitView'"
        :key="mountKey"
      />
    </div>
  </div>
</template>

<script>
import WeekView from '@/components/WeekView.vue'
import QuestionView from '@/components/QuestionView.vue'
import ScatterView from '@/components/ScatterView.vue'
import PortraitView from '@/components/PortraitView.vue'
import {
  REPORT_CHART_LABELS,
  coerceWeekRange,
  ensureReportChartContext,
} from '@/utils/reportCharts.js'

let _chartUid = 0

export default {
  name: 'ReportChartEmbed',
  components: { WeekView, QuestionView, ScatterView, PortraitView },
  props: {
    view: { type: String, required: true },
    params: { type: Object, default: () => ({}) },
    error: { type: String, default: '' },
    chartIndex: { type: Number, default: 0 },
  },
  data() {
    _chartUid += 1
    const uid = _chartUid
    const slug = String(this.view || 'chart')
      .replace(/View$/, '')
      .toLowerCase()
    return {
      containerId: `report-${slug}-${uid}`,
      mountKey: `${slug}-${uid}`,
      contextReady: false,
      contextError: '',
    }
  },
  computed: {
    supported() {
      return ['WeekView', 'QuestionView', 'ScatterView', 'PortraitView'].includes(this.view)
    },
    title() {
      return REPORT_CHART_LABELS[this.view] || this.view
    },
    paramsHint() {
      const p = this.params || {}
      const parts = []
      const wr = coerceWeekRange(p.week_range)
      if (wr) parts.push(`第 ${wr[0]}–${wr[1]} 周`)
      if (Array.isArray(p.title_ids) && p.title_ids.length) {
        parts.push(`锚定 ${p.title_ids.length} 题`)
      } else if (p.knowledge) {
        parts.push(String(p.knowledge))
      }
      if (p.kind != null) parts.push(`簇 ${Number(p.kind) - 1}`)
      if (Array.isArray(p.student_ids) && p.student_ids.length) {
        parts.push(`${p.student_ids.length} 名学生`)
      }
      return parts.join(' · ')
    },
  },
  async mounted() {
    if (!this.supported || this.error) return
    try {
      const result = await ensureReportChartContext(this.$store, this.view, this.params)
      if (!result?.ok) {
        this.contextError = result?.error || '图表上下文未就绪'
        return
      }
      this.contextReady = true
    } catch (err) {
      console.error('ensureReportChartContext failed', err)
      this.contextError = err?.message || '图表加载失败'
    }
  },
}
</script>

<style scoped lang="less">
.report-chart-embed {
  margin: 14px 0;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  background: #fafafa;
  overflow: hidden;
}

.report-chart-embed-head {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 8px;
  padding: 8px 12px;
  background: #f0f4f8;
  border-bottom: 1px solid #e0e0e0;
}

.report-chart-embed-title {
  font-size: 13px;
  font-weight: 600;
  color: #333;
}

.report-chart-embed-hint {
  font-size: 12px;
  color: #666;
}

.report-chart-embed-body {
  padding: 4px;
  max-height: 420px;
  overflow: auto;
}

.report-chart-embed-error,
.report-chart-embed-loading {
  padding: 12px;
  font-size: 13px;
  color: #666;
}

.report-chart-embed-error {
  color: #b45309;
}

.report-chart-embed-body :deep(#week-view),
.report-chart-embed-body :deep(#question-view) {
  margin: 0;
}

.report-chart-embed-body :deep(#week-view.embedded .title),
.report-chart-embed-body :deep(#question-view.embedded .title) {
  display: none;
}

.report-chart-embed-body :deep(#portrait-view .title) {
  display: none;
}

.report-chart-embed-body :deep(.scatter-chart--compact) {
  min-height: 280px;
}
</style>

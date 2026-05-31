<template>
  <div class="agent-report-body">
    <template v-for="(seg, i) in segments" :key="i">
      <AgentMarkdown
        v-if="seg.type === 'md' && seg.content.trim()"
        :source="seg.content"
        class="agent-report-body-md"
        @link-click="$emit('link-click', $event)"
        @report-link-click="$emit('report-link-click', $event)"
      />
      <ReportChartEmbed
        v-else-if="seg.type === 'chart'"
        :view="seg.view"
        :params="seg.params"
        :error="seg.error"
        :chart-index="i"
      />
    </template>
  </div>
</template>

<script>
import AgentMarkdown from '@/components/agent/AgentMarkdown.vue'
import ReportChartEmbed from '@/components/agent/ReportChartEmbed.vue'
import { splitReportMarkdown } from '@/utils/reportCharts.js'

export default {
  name: 'AgentReportBody',
  components: { AgentMarkdown, ReportChartEmbed },
  props: {
    source: { type: String, default: '' },
  },
  emits: ['link-click', 'report-link-click'],
  computed: {
    segments() {
      return splitReportMarkdown(this.source)
    },
  },
}
</script>

<style scoped lang="less">
.agent-report-body {
  font-size: 15px;
  line-height: 1.65;
}

.agent-report-body-md {
  display: block;
}
</style>

<template>
  <AgentPageLayout :context="agentContext" @visual-link-click="onVisualLinkClick" />
</template>

<script>
import AgentPageLayout from '@/components/agent/AgentPageLayout.vue'
import { mapActions, mapGetters } from 'vuex'

export default {
  name: 'AgentView',
  components: { AgentPageLayout },
  mounted() {
    this.fetchClusterData()
  },
  computed: {
    ...mapGetters([
      'getSelectedIds',
      'getNavSelectedClasses',
      'getNavSelectedMajors',
      'getNavWeekRange',
    ]),
    agentContext() {
      return {
        classes: this.getNavSelectedClasses || [],
        majors: this.getNavSelectedMajors || [],
        week_range: this.getNavWeekRange || undefined,
        selected_student_ids: this.getSelectedIds || [],
      }
    },
  },
  methods: {
    ...mapActions(['fetchClusterData', 'syncDashboardFromAgentScope', 'applyAgentVisualLinkNavigation']),
    async onVisualLinkClick({ view, params }) {
      await this.syncDashboardFromAgentScope()
      await this.$router.push('/')
      await this.$nextTick()
      await this.applyAgentVisualLinkNavigation({ view, params: params || {} })
    },
  },
}
</script>

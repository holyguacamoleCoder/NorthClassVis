<template>
  <div class="agent-scope-filter">
    <LoadingSpinner v-if="!scopeLoaded || applying || navScopeApplying" />
    <template v-if="scopeLoaded">
      <div class="agent-scope-dropdowns">
        <div class="agent-scope-dropdown-cell">
          <CheckboxDropdown
            v-if="checkoutClasses.length"
            :items="checkoutClasses"
            title="Class"
            @change="onClassesChange"
          />
        </div>
        <div class="agent-scope-dropdown-cell">
          <CheckboxDropdown
            v-if="checkoutMajors.length"
            :items="checkoutMajors"
            title="Major"
            @change="onMajorsChange"
          />
        </div>
      </div>

      <div v-if="weekReady" class="agent-scope-week">
        <div class="agent-scope-week-head">
          <span class="agent-scope-week-label">{{ ui.railWeekRange }}</span>
          <span class="agent-scope-week-val">第 {{ clampedWeekStart }}–{{ clampedWeekEnd }} 周</span>
          <button type="button" class="agent-scope-week-btn" @click="weekRangeLocked = !weekRangeLocked">
            {{ weekRangeLocked ? ui.railWeekLocked : ui.railWeekUnlock }}
          </button>
        </div>
        <div class="agent-scope-week-track">
          <div class="agent-scope-week-bg" />
          <div class="agent-scope-week-fill" :style="selectedRangeStyle" />
          <div class="agent-scope-week-slider agent-scope-week-slider--left" :style="leftZoneStyle">
            <input
              v-model.number="weekStart"
              type="range"
              :min="weekRangeMin"
              :max="weekRangeMax"
              :disabled="weekRangeLocked || applying"
              @input="onWeekStartInput"
            />
          </div>
          <div class="agent-scope-week-slider agent-scope-week-slider--right" :style="rightZoneStyle">
            <input
              v-model.number="weekEnd"
              type="range"
              :min="weekRangeMin"
              :max="weekRangeMax"
              :disabled="weekRangeLocked || applying"
              @input="onWeekEndInput"
            />
          </div>
        </div>
      </div>

      <p v-if="selectedStudentCount" class="agent-scope-students">
        {{ ui.railSelectedStudents(selectedStudentCount) }}
      </p>
      <p class="agent-scope-hint">{{ ui.railScopeHint }}</p>

      <div class="agent-scope-actions">
        <button
          type="button"
          class="agent-scope-btn agent-scope-btn--primary"
          :disabled="applying"
          @click="applyScope"
        >
          {{ applying ? ui.railApplying : ui.railApplyScope }}
        </button>
        <button type="button" class="agent-scope-btn" @click="$emit('open-dashboard')">
          {{ ui.railOpenViz }}
        </button>
      </div>
    </template>
  </div>
</template>

<script>
import { mapGetters, mapState } from 'vuex'
import config from '@/assets/config/config.json'
import CheckboxDropdown from '@/components/CheckboxDropdown.vue'
import LoadingSpinner from '@/components/LoadingSpinner.vue'
import { getConfig, setConfig } from '@/api/ConfigPanel.js'
import { AGENT_UI } from '@/constants/agentUiText.js'
import { formatFilterSelectionLabel } from '@/utils/filterSelectionLabel.js'

export default {
  name: 'AgentScopeFilter',
  components: { CheckboxDropdown, LoadingSpinner },
  emits: ['open-dashboard', 'scope-applied'],
  data() {
    return {
      ui: AGENT_UI,
      scopeLoaded: false,
      applying: false,
      checkoutClasses: [],
      checkoutMajors: [],
      displayClassesText: '未选',
      displayMajorsText: '未选',
      weekRangeMin: 0,
      weekRangeMax: 0,
      weekStart: 0,
      weekEnd: 0,
      weekRangeLocked: true,
    }
  },
  computed: {
    ...mapGetters(['getSelectedIds', 'getNavWeekRange']),
    ...mapState(['navScopeApplying']),
    selectedStudentCount() {
      return (this.getSelectedIds || []).length
    },
    weekReady() {
      return this.weekRangeMax > this.weekRangeMin
    },
    clampedWeekStart() {
      return this.clampWeek(this.weekStart)
    },
    clampedWeekEnd() {
      return this.clampWeek(this.weekEnd)
    },
    totalSpan() {
      if (!this.weekReady) return 1
      return this.weekRangeMax - this.weekRangeMin
    },
    selectedRangeStyle() {
      const left = ((this.clampedWeekStart - this.weekRangeMin) / this.totalSpan) * 100
      const right = ((this.weekRangeMax - this.clampedWeekEnd) / this.totalSpan) * 100
      return {
        left: `${Math.max(0, Math.min(100, left))}%`,
        right: `${Math.max(0, Math.min(100, right))}%`,
      }
    },
    leftZoneStyle() {
      const mid = (this.clampedWeekStart + this.clampedWeekEnd) / 2
      const pct = ((mid - this.weekRangeMin) / this.totalSpan) * 100
      return { clipPath: `inset(0 ${Math.max(0, 100 - pct)}% 0 0)` }
    },
    rightZoneStyle() {
      const mid = (this.clampedWeekStart + this.clampedWeekEnd) / 2
      const pct = ((mid - this.weekRangeMin) / this.totalSpan) * 100
      return { clipPath: `inset(0 0 0 ${Math.max(0, pct)}%)` }
    },
  },
  watch: {
    '$route.name'(name) {
      if (name === 'agent') this.refreshFromServer()
    },
  },
  mounted() {
    this.refreshFromServer()
  },
  methods: {
    clampWeek(v) {
      if (!this.weekReady) return this.weekRangeMin
      const n = Number(v)
      if (Number.isNaN(n)) return this.weekRangeMin
      return Math.min(this.weekRangeMax, Math.max(this.weekRangeMin, n))
    },
    async refreshFromServer() {
      this.scopeLoaded = false
      await this.loadFromServer()
      this.scopeLoaded = true
    },
    async loadFromServer() {
      try {
        const response = await getConfig()
        if (response.status !== 200) return
        const backendClasses = response.data.classes || []
        const backendMajors = response.data.majors || []
        this.checkoutClasses = config.classes.map((item) => ({
          text: item.text,
          checked: backendClasses.includes(item.text),
        }))
        this.checkoutMajors = config.majors.map((item) => ({
          text: item.text,
          checked: backendMajors.includes(item.text),
        }))
        this.syncDisplayLabels()
        this.applyWeekRangeFromResponse(response.data.week_range)
        this.commitScopeToStore(false)
      } catch (err) {
        console.error('AgentScopeFilter loadFromServer failed', err)
      }
    },
    applyWeekRangeFromResponse(wr, { keepSelection = false } = {}) {
      if (!wr || wr.min === undefined || wr.max === undefined) {
        this.weekRangeMin = 0
        this.weekRangeMax = 0
        return
      }
      const prevStart = this.weekStart
      const prevEnd = this.weekEnd
      this.weekRangeMin = Number(wr.min)
      this.weekRangeMax = Number(wr.max)
      if (!this.weekReady) return

      if (keepSelection) {
        this.weekStart = this.clampWeek(prevStart)
        this.weekEnd = this.clampWeek(prevEnd)
        if (this.weekStart > this.weekEnd) this.weekStart = this.weekEnd
        return
      }

      const storeWr = this.getNavWeekRange
      let start
      let end
      if (Array.isArray(wr.selected) && wr.selected.length >= 2) {
        start = Number(wr.selected[0])
        end = Number(wr.selected[1])
      } else if (Array.isArray(storeWr) && storeWr.length >= 2) {
        start = Number(storeWr[0])
        end = Number(storeWr[1])
      } else {
        start = Math.max(this.weekRangeMin, this.weekRangeMax - 15)
        end = this.weekRangeMax
      }
      this.weekStart = this.clampWeek(start)
      this.weekEnd = this.clampWeek(end)
      if (this.weekStart > this.weekEnd) {
        this.weekStart = this.weekEnd
      }
    },
    syncDisplayLabels() {
      this.displayClassesText = formatFilterSelectionLabel(this.checkoutClasses)
      this.displayMajorsText = formatFilterSelectionLabel(this.checkoutMajors)
    },
    onClassesChange(_selected, text) {
      this.displayClassesText = text
    },
    onMajorsChange(_selected, text) {
      this.displayMajorsText = text
    },
    onWeekStartInput() {
      this.weekStart = this.clampWeek(this.weekStart)
      if (this.weekStart > this.weekEnd) this.weekEnd = this.weekStart
    },
    onWeekEndInput() {
      this.weekEnd = this.clampWeek(this.weekEnd)
      if (this.weekEnd < this.weekStart) this.weekStart = this.weekEnd
    },
    commitScopeToStore(triggerReload) {
      const classes = this.checkoutClasses.filter((i) => i.checked).map((i) => i.text)
      const majors = this.checkoutMajors.filter((i) => i.checked).map((i) => i.text)
      const weekRange = this.weekReady ? [this.clampedWeekStart, this.clampedWeekEnd] : null
      this.$store.commit('setNavScope', {
        classes,
        majors,
        weekRange,
        classesLabel: this.displayClassesText,
        majorsLabel: this.displayMajorsText,
      })
      this.$store.commit('setNavFilter', {
        classes: this.displayClassesText,
        majors: this.displayMajorsText,
      })
      if (triggerReload) {
        this.$store.dispatch('applyNavConfig')
      }
    },
    async applyScope() {
      const selectedClasses = this.checkoutClasses.filter((i) => i.checked).map((i) => i.text)
      const selectedMajors = this.checkoutMajors.filter((i) => i.checked).map((i) => i.text)
      if (!selectedClasses.length || !selectedMajors.length) {
        window.alert('请至少选择一个班级和一个专业')
        return
      }
      this.applying = true
      this.$store.commit('setNavScopeApplying', true)
      try {
        const weekRange = this.weekReady ? [this.clampedWeekStart, this.clampedWeekEnd] : null
        const data = await setConfig(selectedClasses, selectedMajors, weekRange)
        if (data.status === 200) {
          this.weekRangeLocked = true
          this.commitScopeToStore(true)
          this.$emit('scope-applied')
        }
      } catch (err) {
        console.error('applyScope failed', err)
        this.$store.commit('setNavScopeApplying', false)
      } finally {
        this.applying = false
      }
    },
  },
}
</script>

<style scoped lang="less">
.agent-scope-filter {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-height: 120px;
}

.agent-scope-dropdowns {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  align-items: start;
}

.agent-scope-dropdown-cell {
  min-width: 0;
  :deep(.dd-trigger) {
    width: 100%;
  }
  :deep(.dd-trigger-container) {
    width: 100%;
  }
  :deep(.dd-trigger-container .dd-default-trigger) {
    width: 100% !important;
    max-width: 100%;
    font-size: 13px;
  }
  :deep(.dd-caret-down) {
    margin-left: 4px !important;
  }
  :deep(.tag) {
    font-size: 11px;
  }
}

.agent-scope-week {
  padding: 8px 0 4px;
  border-top: 1px solid #eef1f5;
}

.agent-scope-week-head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  margin-bottom: 6px;
}

.agent-scope-week-label {
  font-weight: 600;
  color: #555;
}

.agent-scope-week-val {
  color: #333;
  flex: 1;
  min-width: 88px;
}

.agent-scope-week-btn {
  border: none;
  border-radius: 4px;
  padding: 2px 8px;
  font-size: 11px;
  color: #fff;
  background: #377eb8;
  cursor: pointer;
  white-space: nowrap;
}

.agent-scope-week-track {
  position: relative;
  height: 28px;
}

.agent-scope-week-bg {
  position: absolute;
  left: 0;
  right: 0;
  top: 10px;
  height: 6px;
  background: #e8eaee;
  border-radius: 999px;
}

.agent-scope-week-fill {
  position: absolute;
  top: 10px;
  height: 6px;
  background: #8fc4ff;
  border-radius: 999px;
  pointer-events: none;
}

.agent-scope-week-slider {
  position: absolute;
  left: 0;
  right: 0;
  top: 0;
  bottom: 0;
  input {
    width: 100%;
    height: 28px;
    margin: 0;
    -webkit-appearance: none;
    background: transparent;
    &::-webkit-slider-thumb {
      -webkit-appearance: none;
      width: 14px;
      height: 14px;
      border-radius: 50%;
      background: #377eb8;
      border: 2px solid #fff;
      cursor: pointer;
    }
  }
  &--left { z-index: 2; }
  &--right { z-index: 1; }
}

.agent-scope-students {
  margin: 0;
  font-size: 12px;
  color: #377eb8;
  font-weight: 500;
}

.agent-scope-hint {
  margin: 0;
  font-size: 11px;
  color: #999;
  line-height: 1.45;
}

.agent-scope-actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.agent-scope-btn {
  width: 100%;
  padding: 8px 10px;
  border: 1px solid #dde3ea;
  border-radius: 6px;
  background: #fff;
  font-size: 13px;
  color: #377eb8;
  cursor: pointer;
  &:hover:not(:disabled) { background: #f0f7ff; }
  &:disabled { opacity: 0.6; cursor: wait; }
  &--primary {
    background: #377eb8;
    border-color: #377eb8;
    color: #fff;
    &:hover:not(:disabled) { background: #2a6294; }
  }
}
</style>

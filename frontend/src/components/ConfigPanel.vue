<template>
  <div class="config-container">
    <div class="config-panel">
      <LoadingSpinner v-if="loading" />

      <div class="config-panel-title">
        <div class="config-panel-title-icon"></div>
        <span class="config-panel-title-text">Cluster Configuration</span>
      </div>
      <div class="config-panel-checkbox">
        <CheckboxDropdown v-if="CheckoutClasses" :items="CheckoutClasses" title="Class" @change="updateSelectedClasses"/>
        <CheckboxDropdown v-if="CheckoutMajors" :items="CheckoutMajors" title="Major" @change="updateSelectedMajors"/>
      </div>

      <div class="config-panel-week-range" v-if="weekRangeMax >= weekRangeMin">
        <span class="week-range-label">第 X~Y 周:</span>
        <span class="week-range-value">第 {{ weekStart }} 周 ~ 第 {{ weekEnd }} 周</span>
        <span class="week-range-size">窗口大小：{{ weekWindowSize }} 周</span>
        <button class="week-edit-btn" @click="toggleWeekEdit">
          {{ weekRangeLocked ? '调整周范围' : '锁定周范围' }}
        </button>
        <div class="week-range-track-wrap">
          <div class="week-range-track-bg"></div>
          <div class="week-range-track-selected" :style="selectedRangeStyle"></div>
          <div class="week-slider-zone week-slider-left" :style="leftZoneStyle">
            <input type="range" :min="weekRangeMin" :max="weekRangeMax" v-model.number="weekStart"
              :disabled="weekRangeLocked || loading"
              @input="onWeekStartInput" />
          </div>
          <div class="week-slider-zone week-slider-right" :style="rightZoneStyle">
            <input type="range" :min="weekRangeMin" :max="weekRangeMax" v-model.number="weekEnd"
              :disabled="weekRangeLocked || loading"
              @input="onWeekEndInput" />
          </div>
        </div>
      </div>

      <div class="config-panel-main">
        <button class="close-button" @click="closePanel">Close</button>
        <button class="submit-button" @click="submitConfigData">Submit</button>
      </div>
    </div>
  </div>
</template>

<script>
import config from '@/assets/config/config.json'
import CheckboxDropdown from './CheckboxDropdown.vue'
import LoadingSpinner from './LoadingSpinner.vue'
import { setConfig, getConfig } from '@/api/ConfigPanel.js'
import { mapActions } from 'vuex'
export default {
  name: 'ConfigPanel',
  components: {
    CheckboxDropdown,
    LoadingSpinner
  },
  data() {
    return {
      loading: false,
      CheckoutClasses: [],
      CheckoutMajors: [],
      displayClassesText: 'Part',
      displayMajorsText: 'All',
      weekRangeMin: 0,
      weekRangeMax: 0,
      weekStart: 0,
      weekEnd: 0,
      weekRangeLocked: true
    }
  },
  async created(){
    const response = await getConfig()
    if (response.status === 200) {
      const backendClasses = response.data.classes
      const backendMajors = response.data.majors

      // 初始化所有项为 checked: false
      this.CheckoutClasses = config.classes.map(item => ({
        text: item.text,
        checked: backendClasses.includes(item.text)
      }))

      this.CheckoutMajors = config.majors.map(item => ({
        text: item.text,
        checked: backendMajors.includes(item.text)
      }))
      const wr = response.data.week_range
      if (wr && wr.min !== undefined && wr.max !== undefined) {
        this.weekRangeMin = wr.min
        this.weekRangeMax = wr.max
        const sel = wr.selected
        const defStart = Math.max(this.weekRangeMin, wr.max - 15)
        this.weekStart = Array.isArray(sel) && sel.length >= 2 ? Math.max(this.weekRangeMin, sel[0]) : defStart
        this.weekEnd = Array.isArray(sel) && sel.length >= 2 ? Math.min(this.weekRangeMax, sel[1]) : wr.max
        if (this.weekStart > this.weekEnd) this.weekStart = this.weekEnd
      }
      console.log('Config loaded successfully');
    } else {
      console.error('Failed to fetch config data:', response);
    }
  },
  mounted(){
  },
  computed: {
    totalSpan() {
      const s = this.weekRangeMax - this.weekRangeMin
      return s <= 0 ? 1 : s
    },
    weekWindowSize() {
      return Math.max(1, this.weekEnd - this.weekStart + 1)
    },
    selectedRangeStyle() {
      const left = ((this.weekStart - this.weekRangeMin) / this.totalSpan * 100)
      const right = ((this.weekRangeMax - this.weekEnd) / this.totalSpan * 100)
      return {
        left: `${Math.max(0, left)}%`,
        right: `${Math.max(0, right)}%`
      }
    },
    leftZoneStyle() {
      const mid = (this.weekStart + this.weekEnd) / 2
      const pct = ((mid - this.weekRangeMin) / this.totalSpan * 100)
      return { clipPath: `inset(0 ${100 - pct}% 0 0)` }
    },
    rightZoneStyle() {
      const mid = (this.weekStart + this.weekEnd) / 2
      const pct = ((mid - this.weekRangeMin) / this.totalSpan * 100)
      return { clipPath: `inset(0 0 0 ${pct}%)` }
    }
  },
  methods: {
    ...mapActions(['updateConfig']),
    updateSelectedClasses(selectedClasses, text) {
      this.displayClassesText = text
    },
    updateSelectedMajors(selectedMajors, text) {
      this.displayMajorsText = text
    },
    toggleWeekEdit() {
      this.weekRangeLocked = !this.weekRangeLocked
    },
    onWeekStartInput() {
      if (this.weekStart > this.weekEnd) this.weekEnd = this.weekStart
    },
    onWeekEndInput() {
      if (this.weekEnd < this.weekStart) this.weekStart = this.weekEnd
    },
    async submitConfigData(){
      const selectedClasses = this.CheckoutClasses.filter(item => item.checked).map(item => item.text)      
      const selectedMajors = this.CheckoutMajors.filter(item => item.checked).map(item => item.text)
      if(selectedClasses.length === 0){
        alert('Please select at least one class.')
        return
      }
      if(selectedMajors.length === 0) {
        alert('Please select at least one major.')
        return
      }
      console.log('Selected Classes:', selectedClasses)
      console.log('Selected Majors:', selectedMajors)
      this.loading =  true
      const weekRange = (this.weekRangeMax >= this.weekRangeMin)
        ? [this.weekStart, this.weekEnd] : null
      const data  = await setConfig(selectedClasses, selectedMajors, weekRange)
      if(data.status === 200){
        console.log('Config updated successfully')
        // this.closePanel()
        this.$store.commit('SET_CONFIG_LOADED', Date.now()); // 重置状态以触发重新加载
        this.weekRangeLocked = true
        this.loading = false
        this.closePanel()
      }
    },
    closePanel() {
      this.$emit('close', this.displayClassesText, this.displayMajorsText)
    }
  }
};
</script>

<style scoped lang="less">
*{
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}
@config-panel-width: 400px;
@config-panel-height: 320px;
.config-container{
  z-index: 100;
  position: relative;
  height: @config-panel-height;
  width: @config-panel-width;
  border: 1px solid #ccc;
  border-radius: 10px;
  background-color: #fff;
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1); /* 添加阴影 */
  .config-panel-title{
    height: 50px;
    margin-bottom: 10px;
    .config-panel-title-icon{
      float: left;
      height: 50px;
      width: 50px;
      background: no-repeat center/60% url('@/assets/images/settings.png') #fff;
    }
    .config-panel-title-text{
      font-size: 20px;
      font-weight: bold;
      line-height: 50px;
    }
  }
  .config-panel-checkbox{
    height: 80px;
    padding: 10px 30px;
  }
  .config-panel-week-range{
    padding: 8px 30px;
    .week-range-label{ font-weight: bold; margin-right: 8px; }
    .week-range-value{ color: #333; font-size: 13px; margin-right: 8px; }
    .week-range-size{ color: #666; font-size: 12px; }
    .week-edit-btn{
      margin-left: 8px;
      border: none;
      border-radius: 6px;
      padding: 2px 8px;
      font-size: 12px;
      color: #fff;
      background: #4a90d9;
      cursor: pointer;
    }
    .week-range-track-wrap{
      position: relative;
      height: 32px;
      margin-top: 8px;
      display: flex;
      align-items: center;
      .week-range-track-bg{
        position: absolute;
        left: 0;
        right: 0;
        height: 8px;
        background: #e0e0e0;
        border-radius: 999px;
        pointer-events: none;
      }
      .week-range-track-selected{
        position: absolute;
        height: 8px;
        background: #8fc4ff;
        border-radius: 999px;
        pointer-events: none;
      }
      .week-slider-zone{
        position: absolute;
        left: 0;
        right: 0;
        top: 0;
        bottom: 0;
        input{
          width: 100%;
          height: 32px;
          margin: 0;
          -webkit-appearance: none;
          background: transparent;
          &::-webkit-slider-runnable-track{
            height: 8px;
            background: transparent;
            border-radius: 4px;
          }
          &::-webkit-slider-thumb{
            -webkit-appearance: none;
            width: 18px;
            height: 18px;
            border-radius: 50%;
            background: #2f7fda;
            border: 2px solid #ffffff;
            box-shadow: 0 1px 4px rgba(0, 0, 0, 0.25);
            cursor: pointer;
            margin-top: -5px;
          }
          &::-moz-range-track{
            height: 8px;
            background: transparent;
            border-radius: 4px;
          }
          &::-moz-range-thumb{
            width: 18px;
            height: 18px;
            border-radius: 50%;
            background: #2f7fda;
            border: 2px solid #ffffff;
            box-shadow: 0 1px 4px rgba(0, 0, 0, 0.25);
            cursor: pointer;
          }
        }
        input:disabled{
          opacity: 0.5;
          cursor: not-allowed;
        }
      }
      .week-slider-left{ z-index: 2; }
      .week-slider-right{ z-index: 1; }
    }
  }
  .config-panel-main{
    .close-button
    ,.submit-button{
      width: 150px; 
      font-size: 20px;
      margin-top: 10px;
      margin-left: 17px;
      margin-bottom:10px;
      border-radius: 5px;
      background-color: #ccc;
      padding: 5px;
      color: #fff;
      font-weight: bold;
      border: none;
      cursor: pointer;
    }
  }
}

</style>
<template>
  <div id="scatter-chart" :class="{ 'scatter-chart--compact': compact }">
    <div v-if="!hideChrome" class="scatter-chrome">
      <div class="scatter-chrome-row scatter-chrome-row--head">
        <span class="scatter-title">Scatter View</span>
        <div class="scatter-legend">
          <span v-for="(color, i) in getColors" :key="i" class="scatter-legend-item">
            <i class="scatter-legend-dot" :style="{ background: color }" />{{ i }}
          </span>
        </div>
        <div class="scatter-toolbar">
          <button
            type="button"
            class="click-button"
            :class="{ 'scatter-tool--active': clickEnabled && !brushEnabled }"
            title="点选学生"
            @click="setClickMode"
          />
          <button
            type="button"
            class="brush-button"
            :class="{ 'scatter-tool--active': brushEnabled }"
            title="框选学生"
            @click="setBrushMode"
          />
        </div>
      </div>
      <div v-if="showIdPicker" class="scatter-chrome-row scatter-chrome-row--pick">
        <input
          v-model="idInputText"
          type="text"
          class="scatter-id-input"
          :placeholder="idPickerPlaceholder"
          :disabled="loading"
          @keydown.enter.prevent="applyIdsByInput('replace')"
        />
        <div class="scatter-id-btns">
          <button type="button" class="scatter-id-btn scatter-id-btn--primary" :disabled="loading" @click="applyIdsByInput('replace')">选中</button>
          <button type="button" class="scatter-id-btn" :disabled="loading" @click="applyIdsByInput('append')">追加</button>
          <button type="button" class="scatter-id-btn" :disabled="loading" @click="clearIdSelection">清空</button>
        </div>
      </div>
      <p v-if="showIdPicker && idPickerMessage" class="scatter-id-picker-msg">{{ idPickerMessage }}</p>
    </div>
    <div
      v-else-if="showIdPicker"
      class="scatter-id-picker scatter-id-picker--compact"
    >
      <div class="scatter-chrome-row scatter-chrome-row--pick">
        <input
          v-model="idInputText"
          type="text"
          class="scatter-id-input"
          :placeholder="idPickerPlaceholder"
          :disabled="loading"
          @keydown.enter.prevent="applyIdsByInput('replace')"
        />
        <div class="scatter-id-btns">
          <button type="button" class="scatter-id-btn scatter-id-btn--primary" :disabled="loading" @click="applyIdsByInput('replace')">选中</button>
          <button type="button" class="scatter-id-btn" :disabled="loading" @click="applyIdsByInput('append')">追加</button>
          <button type="button" class="scatter-id-btn" :disabled="loading" @click="clearIdSelection">清空</button>
        </div>
      </div>
      <p v-if="idPickerMessage" class="scatter-id-picker-msg">{{ idPickerMessage }}</p>
    </div>
    <div class="scatter-viz-wrap" :class="{ 'scatter-viz-wrap--compact': compact }">
      <div :id="containerId" ref="visualizationRoot" class="scatter-viz-host" />
      <LoadingSpinner v-if="loading && !hideLoadingOverlay" />
    </div>
  </div>
</template>

<script>
import { getScatterData } from '@/api/ScatterView'
import { mapState, mapActions, mapGetters } from 'vuex'
import LoadingSpinner from './LoadingSpinner.vue'
export default {
  name: 'ScatterView',
  emits: ['loading-change'],
  props: {
    containerId: { type: String, default: 'visualizationS' },
    compact: { type: Boolean, default: false },
    hideChrome: { type: Boolean, default: false },
    /** 由父级（如 Agent 右栏）统一展示 LoadingSpinner 时设为 true */
    hideLoadingOverlay: { type: Boolean, default: false },
    /** 学号/ID 文本框指定选中 */
    showIdPicker: { type: Boolean, default: true },
  },
  data() {
    return {
      idInputText: '',
      idPickerMessage: '',
      loading: false,
      svg: null,
      g: null,
      gPoints: null,
      gBrush: null,
      xScale: null,
      yScale: null,
      tooltip: null,
      brushing: null,
      batchSize: 100, // 每批加载的数据量
      currentBatch: 0, // 当前批次索引
      totalBatches: 0, // 总批次数
      allData: [], // 所有数据
      renderedData: [], // 已渲染的数据
      clickedStudent: new Set(),
      brushedStudent: new Set(),
      brushEnabled: false,
      clickEnabled: true,
      _renderToken: 0,
    }
  },
  components: {
    LoadingSpinner
  },
  async mounted() {
    await this.loadData({ preserveSelection: true })
  },
  computed: {
    ...mapState(['configLoaded', 'navConfigRevision']),
    ...mapGetters(['getColors', 'getSelectedIds']),
    idPickerPlaceholder() {
      return this.compact ? '学号，逗号分隔' : '学号/ID，逗号或空格分隔'
    },
    chartLayout() {
      if (this.compact) {
        return {
          width: 328,
          height: 228,
          margin: { top: 14, right: 10, bottom: 10, left: 24 },
        }
      }
      return {
        width: 360,
        height: 500,
        margin: { top: 22, right: 8, bottom: 8, left: 26 },
      }
    },
  },
  methods: {
    ...mapActions(['toggleSelectedIds']),
    chartInnerSize() {
      const { width, height, margin } = this.chartLayout
      return {
        width: width - margin.right - margin.left,
        height: height - margin.top - margin.bottom,
      }
    },
    syncSelectionToStore() {
      const ids = Array.from(new Set([...this.clickedStudent, ...this.brushedStudent]))
      this.toggleSelectedIds(ids)
    },
    parseIdInput(text) {
      return String(text || '')
        .split(/[\s,;，；\n]+/)
        .map((s) => s.trim())
        .filter(Boolean)
    },
    buildStudentIdIndex() {
      const exact = new Map()
      const suffix = new Map()
      for (const d of this.allData) {
        const id = String(d.student_id)
        exact.set(id.toLowerCase(), id)
        const s5 = id.slice(-5).toLowerCase()
        if (!suffix.has(s5)) {
          suffix.set(s5, id)
        } else if (suffix.get(s5) !== id) {
          suffix.set(s5, null)
        }
      }
      return { exact, suffix }
    },
    resolveStudentTokens(tokens) {
      const { exact, suffix } = this.buildStudentIdIndex()
      const found = []
      const missing = []
      const seen = new Set()
      for (const raw of tokens) {
        const key = raw.toLowerCase()
        let id = exact.get(key)
        if (!id && raw.length >= 4) {
          const hit = suffix.get(raw.slice(-5).toLowerCase())
          if (hit) id = hit
        }
        if (id) {
          if (!seen.has(id)) {
            seen.add(id)
            found.push(id)
          }
        } else {
          missing.push(raw)
        }
      }
      return { found, missing }
    },
    applySelectionIds(ids, { message } = {}) {
      const visible = new Set(this.allData.map((d) => d.student_id))
      const valid = ids.filter((id) => visible.has(id))
      const skipped = ids.length - valid.length
      this.clickedStudent = new Set(valid)
      this.brushedStudent.clear()
      this.syncSelectionToStore()
      this.updateCircles()
      if (message != null) {
        this.idPickerMessage = message
      } else if (valid.length) {
        let msg = `已选 ${valid.length} 人`
        if (skipped > 0) msg += `（${skipped} 人不在当前散点范围）`
        this.idPickerMessage = msg
      } else {
        this.idPickerMessage = '未匹配到学生，请检查学号或先应用班级/专业筛选'
      }
    },
    applyIdsByInput(mode = 'replace') {
      const tokens = this.parseIdInput(this.idInputText)
      if (!tokens.length) {
        this.idPickerMessage = '请输入至少一个学号'
        return
      }
      const { found, missing } = this.resolveStudentTokens(tokens)
      let ids = found
      if (mode === 'append') {
        ids = [...new Set([...(this.getSelectedIds || []), ...found])]
      }
      if (!ids.length) {
        this.idPickerMessage = missing.length
          ? `未匹配: ${missing.join(', ')}`
          : '未匹配到学生'
        return
      }
      let msg = `已选 ${ids.length} 人`
      if (missing.length) msg += `；未匹配: ${missing.join(', ')}`
      this.applySelectionIds(ids, { message: msg })
    },
    clearIdSelection() {
      this.idInputText = ''
      this.idPickerMessage = ''
      this.clickedStudent.clear()
      this.brushedStudent.clear()
      this.syncSelectionToStore()
      this.updateCircles()
    },
    setClickMode() {
      this.clickEnabled = true
      this.brushEnabled = false
      this.brushedStudent.clear()
      this.updateBrushing()
      this.updateCircles()
    },
    setBrushMode() {
      this.brushEnabled = true
      this.clickEnabled = false
      this.updateBrushing()
      this.updateCircles()
    },
    toggleBrush() {
      if (this.brushEnabled) {
        this.setClickMode()
      } else {
        this.setBrushMode()
      }
    },
    toggleClick() {
      if (this.clickEnabled && !this.brushEnabled) {
        this.setBrushMode()
      } else {
        this.setClickMode()
      }
    },
    onPointClick(e, d) {
      if (!this.clickEnabled || this.brushEnabled) return
      e.stopPropagation()
      if (this.clickedStudent.has(d.student_id)) {
        this.clickedStudent.delete(d.student_id)
      } else {
        this.clickedStudent.add(d.student_id)
      }
      this.updateCircles()
      this.syncSelectionToStore()
    },
    attachCircleInteraction(selection) {
      const canClick = this.clickEnabled && !this.brushEnabled
      selection
        .style('cursor', canClick ? 'pointer' : 'default')
        .style('pointer-events', canClick ? 'all' : 'none')
        .on('click', canClick ? (e, d) => this.onPointClick(e, d) : null)
        .on('mouseover', (e, d) => {
          if (!this.tooltip) return
          this.tooltip
            .style('visibility', 'visible')
            .html(`student: ${d.student_id} <br>cluster: ${d.cluster}`)
            .style('left', `${e.pageX + 10}px`)
            .style('top', `${e.pageY + 10}px`)
        })
        .on('mouseout', () => {
          if (!this.tooltip) return
          this.tooltip.style('visibility', 'hidden')
        })
    },
    updateCircleInteraction() {
      if (!this.gPoints) return
      this.attachCircleInteraction(this.gPoints.selectAll('.circle-scatter'))
    },
    detachBrush() {
      if (!this.gBrush) return
      this.gBrush.on('.brush', null)
      this.gBrush.selectAll('*').remove()
    },
    updateChart(event) {
      if (!event.selection) return
      function isBrushed(brush_coords, cx, cy) {
           var x0 = brush_coords[0][0],
               x1 = brush_coords[1][0],
               y0 = brush_coords[0][1],
               y1 = brush_coords[1][1];
          return x0 <= cx && cx <= x1 && y0 <= cy && cy <= y1;    // This return TRUE or FALSE depending on if the points is in the selected area
      }
      const extent = event.selection
      const circles = this.gPoints.selectAll('.circle-scatter')
      circles
      .classed("selected", (d) =>{ 
        const selected = isBrushed(extent, this.xScale(d.transform.x), this.yScale(d.transform.y))
        if (selected) {
          // console.log(d.student_id)
          this.brushedStudent.add(d.student_id)
        }
        // console.log(this.brushedStudent)
        return selected
      })
      this.updateCircles()
    },
    chartRoot() {
      return this.$refs.visualizationRoot
    },
    applyStoreSelection() {
      if (!this.gPoints || !this.allData.length) return
      const ids = this.getSelectedIds || []
      const visible = new Set(this.allData.map((d) => d.student_id))
      this.clickedStudent = new Set(ids.filter((id) => visible.has(id)))
      this.updateCircles()
    },
    async initChart(renderToken) {
      const d3 = this.$d3
      const root = this.chartRoot()
      if (!root) return
      const { width, height, margin } = this.chartLayout
      const lowerBound = -5
      const upperBound = 5

      d3.select(root).selectAll('*').remove()

      this.svg = d3.select(root)
          .append("svg")
          .attr("width", width)
          .attr("height", height)
      this.g = this.svg.append("g")
          .attr("transform", `translate(${margin.left},${margin.top})`)
      this.gPoints = this.g.append("g").attr("class", "points-layer")
      this.gBrush = this.g.append("g").attr("class", "brush-layer")

      // 定义x轴和y轴比例尺
      this.xScale = d3.scaleLinear()
          .domain([lowerBound, upperBound])
          .range([0, width - margin.right - margin.left])

      this.yScale = d3.scaleLinear()
          .domain([lowerBound, upperBound])
          .range([height - margin.top - margin.bottom, margin.top])

      // 创建tooltip
      this.tooltip = d3.select(root).append('div')
          .attr('class', 'tooltip')
          .style('position', 'absolute')
          .style('visibility', 'hidden') 
          .style('background-color', 'white')
          .style('border', '1px solid black')
          .style('padding', '5px')
          .style('z-index', 10)
      

      this.currentBatch = 0
      this.renderedData = []
      this.totalBatches = Math.ceil(this.allData.length / this.batchSize)
      this.renderNextBatch(renderToken)

      // 绘制坐标轴
      // const xAxis = d3.axisBottom(this.xScale)
      // const yAxis = d3.axisLeft(this.yScale)
      
      this.g.append('g')
          .attr('transform', `translate(0,${height - margin.top - margin.bottom})`)
      
      const { width: innerW, height: innerH } = this.chartInnerSize()
      this.brushing = d3
        .brush()
        .filter(() => this.brushEnabled)
        .extent([
          [0, 0],
          [innerW, innerH],
        ])
        .on('start', () => {
          if (!this.brushEnabled) return
          this.brushedStudent.clear()
        })
        .on('brush', (event) => {
          if (!this.brushEnabled) return
          this.updateChart(event)
        })
        .on('end', (event) => {
          if (!this.brushEnabled) return
          if (!event.selection) {
            this.brushedStudent.clear()
          } else {
            this.updateChart(event)
          }
          this.syncSelectionToStore()
        })
      this.updateBrushing()
    },
    renderNextBatch(renderToken) {
      if (renderToken !== this._renderToken) return
      if (!this.g) return
      if (this.currentBatch >= this.totalBatches) {
        this.applyStoreSelection()
        this.updateBrushing()
        this.updateCircleInteraction()
        return
      }

      const start = this.currentBatch * this.batchSize
      const end = Math.min(start + this.batchSize, this.allData.length)
      const batchData = this.allData.slice(start, end)

      this.renderedData.push(...batchData) // 将当前批次的数据添加到渲染数据中

      // 使用 enter-update-exit 模式
      const circles = this.gPoints.selectAll('.circle-scatter')
          .data(this.renderedData, d => d.student_id)

      circles.enter().append('circle')
          .attr('class', 'circle-scatter')
          .merge(circles)
          .attr('cx', d => this.xScale(d.transform.x))
          .attr('cy', d => this.yScale(d.transform.y))
          .attr('r', d => this.clickedStudent.has(d.student_id) || this.brushedStudent.has(d.student_id) ? 8 : 5)
          .attr('fill', d => this.getColors[d.cluster])
          .attr('stroke', d => this.clickedStudent.has(d.student_id) || this.brushedStudent.has(d.student_id) ? 'black' : 'none')
          .attr('stroke-width', d => this.clickedStudent.has(d.student_id) || this.brushedStudent.has(d.student_id) ? 2 : 1)
          .attr('opacity', d => this.clickedStudent.has(d.student_id) || this.brushedStudent.has(d.student_id) ? 1 : 0.8)
      circles.exit().remove()
      this.attachCircleInteraction(this.gPoints.selectAll('.circle-scatter'))

      this.currentBatch++
      setTimeout(() => this.renderNextBatch(renderToken), 0)
    },
    updateCircles() {
      // 使用 enter-update-exit 模式
      const circles = this.gPoints.selectAll('.circle-scatter')
          .data(this.renderedData, d => d.student_id)

      circles.enter().append('circle')
          .attr('class', 'circle-scatter')
          .merge(circles)
          .attr('cx', d => this.xScale(d.transform.x))
          .attr('cy', d => this.yScale(d.transform.y))
          .attr('r', d => this.clickedStudent.has(d.student_id) || this.brushedStudent.has(d.student_id) ? 8 : 5)
          .attr('fill', d => this.getColors[d.cluster])
          .attr('stroke', d => this.clickedStudent.has(d.student_id) || this.brushedStudent.has(d.student_id) ? 'black' : 'none')
          .attr('stroke-width', d => this.clickedStudent.has(d.student_id) || this.brushedStudent.has(d.student_id) ? 2 : 1)
          .attr('opacity', d => this.clickedStudent.has(d.student_id) || this.brushedStudent.has(d.student_id) ? 1 : 0.8)
      circles.exit().remove()
      this.attachCircleInteraction(this.gPoints.selectAll('.circle-scatter'))
    },
    updateBrushing() {
      if (!this.gBrush) return
      if (!this.brushEnabled) {
        this.detachBrush()
        this.gBrush.style('pointer-events', 'none')
        return
      }
      if (!this.brushing) return
      const { width: innerW, height: innerH } = this.chartInnerSize()
      this.brushing.extent([
        [0, 0],
        [innerW, innerH],
      ])
      this.gBrush.style('pointer-events', 'all')
      this.gBrush.call(this.brushing)
      this.updateCircleInteraction()
    },
    clearChartDom() {
      const root = this.chartRoot()
      if (!root) return
      this.$d3.select(root).selectAll('*').remove()
      this.svg = null
      this.g = null
      this.gPoints = null
      this.gBrush = null
      this.brushing = null
      this.xScale = null
      this.yScale = null
      this.tooltip = null
    },
    async loadData(options = {}) {
      const { preserveSelection = false } = options
      const renderToken = ++this._renderToken
      this.loading = true
      this.brushEnabled = false
      this.clickEnabled = true
      this.brushedStudent.clear()
      if (!preserveSelection) {
        this.clickedStudent.clear()
      }
      this.clearChartDom()
      try {
        const { data } = await getScatterData()
        if (renderToken !== this._renderToken) return
        this.currentBatch = 0
        this.totalBatches = 0
        this.renderedData = []
        this.allData = data || []
        await this.$nextTick()
        if (renderToken !== this._renderToken) return
        this.clearChartDom()
        this.initChart(renderToken)
      } catch (err) {
        console.error('ScatterView loadData failed', err)
        if (renderToken === this._renderToken) {
          this.clearChartDom()
        }
      } finally {
        if (renderToken === this._renderToken) {
          this.loading = false
        }
      }
    },
  },
  watch: {
    loading(value) {
      this.$emit('loading-change', value)
    },
    navConfigRevision() {
      this.loadData({ preserveSelection: true })
    },
    getSelectedIds: {
      handler() {
        this.applyStoreSelection()
      },
      deep: true,
    },
    brushEnabled() {
      this.updateBrushing()
    },
    clickEnabled() {
      this.updateCircleInteraction()
    },
  },
}
</script>


<style scoped lang="less">
#scatter-chart {
  display: flex;
  flex-direction: column;
  height: 100%;
  box-sizing: border-box;

  .scatter-chrome {
    flex-shrink: 0;
    border-bottom: 1px solid #ddd;
    background: #fafbfc;
  }

  .scatter-chrome-row {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 0 10px;
    box-sizing: border-box;
  }

  .scatter-chrome-row--head {
    min-height: 36px;
    padding-top: 6px;
    padding-bottom: 6px;
  }

  .scatter-chrome-row--pick {
    padding-bottom: 6px;
    gap: 6px;
  }

  .scatter-title {
    font-size: 15px;
    font-weight: 700;
    line-height: 1.2;
    flex-shrink: 0;
    color: #222;
  }

  .scatter-legend {
    flex: 1;
    min-width: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-wrap: wrap;
    gap: 6px 10px;
  }

  .scatter-legend-item {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    font-size: 11px;
    color: #555;
    white-space: nowrap;
  }

  .scatter-legend-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    flex-shrink: 0;
  }

  .scatter-toolbar {
    display: flex;
    align-items: center;
    gap: 6px;
    flex-shrink: 0;
  }

  .brush-button,
  .click-button {
    height: 22px;
    width: 22px;
    border: 1px solid #ccc;
    border-radius: 4px;
    background-color: #fff;
    cursor: pointer;
    padding: 0;
    flex-shrink: 0;
    &:hover { background-color: #f0f4f8; }
    &.scatter-tool--active {
      border-color: #377eb8;
      background-color: #e8f2fc;
      box-shadow: inset 0 0 0 1px #377eb8;
    }
  }
  .brush-button {
    background: no-repeat center/85% url('@/assets/images/brush.png');
  }
  .click-button {
    background: no-repeat center/100% url('@/assets/images/click.png');
  }

  .scatter-id-picker--compact {
    flex-shrink: 0;
    padding: 0 0 4px;
  }

  .scatter-id-input {
    flex: 1;
    min-width: 0;
    box-sizing: border-box;
    border: 1px solid #ccc;
    border-radius: 4px;
    padding: 4px 8px;
    font-size: 11px;
    line-height: 1.3;
    background: #fff;
    &:focus {
      outline: none;
      border-color: #377eb8;
    }
    &:disabled {
      background: #f5f5f5;
    }
  }

  .scatter-id-btns {
    display: flex;
    flex-shrink: 0;
    gap: 4px;
  }

  .scatter-id-btn {
    border: 1px solid #ccc;
    border-radius: 4px;
    background: #fff;
    padding: 3px 8px;
    font-size: 11px;
    line-height: 1.2;
    cursor: pointer;
    white-space: nowrap;
    &:hover:not(:disabled) { background: #f0f4f8; }
    &:disabled {
      opacity: 0.55;
      cursor: not-allowed;
    }
    &--primary {
      border-color: #377eb8;
      background: #377eb8;
      color: #fff;
      &:hover:not(:disabled) { background: #2d6ba3; }
    }
  }

  .scatter-id-picker-msg {
    margin: 0;
    padding: 0 10px 4px;
    font-size: 10px;
    line-height: 1.3;
    color: #666;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .scatter-viz-wrap {
    flex: 1;
    min-height: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 4px 6px 6px;
    box-sizing: border-box;
  }

  .scatter-viz-host {
    position: relative;
    margin: 0;
    padding: 0;
    box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
    .axis{
      pointer-events: none;
    }
    path{
      z-index:5;
      &.selected{
        stroke: #000;
        stroke-width: 5px;
      }
    }
  }
}

.scatter-viz-wrap {
  position: relative;
  min-height: 0;
}

.scatter-viz-wrap--compact {
  min-height: 228px;
}

.scatter-viz-wrap--compact :deep(.loading-spinner) {
  height: 100%;
  border-radius: 6px;
}

.scatter-chart--compact .scatter-viz-host {
  margin: 0;
  padding: 0;
  box-shadow: none;
}

</style>


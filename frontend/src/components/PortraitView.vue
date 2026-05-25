<template>
  <div id="portrait-view">
    <div class="title">
      <span class="portrait-title-text">Portrait View</span>
      <span v-if="selectionSummary" class="portrait-summary-chip">{{ selectionSummary }}</span>
    </div>
    <div class="vis-container">
      <div class="vis-panel">
        <LoadingSpinner v-if="loading" />
        <div
          v-for="kind in clusterKinds"
          :key="kind"
          class="portrait-cluster-slot"
        >
          <div class="portrait-cluster-chart">
            <div :id="'visualization' + kind" class="portrait-viz-host"></div>
          </div>
          <div class="portrait-cluster-caption">
            <p class="caption-line caption-line--rep">
              <span class="caption-tag" :style="{ background: getColors[kind] }">簇 {{ kind }}</span>
              <span class="caption-rep-label">代表学生</span>
              <span class="caption-id">{{ shortId(clusterCenterByKind[kind]) || '—' }}</span>
            </p>
            <p class="caption-line caption-line--stat">
              <template v-if="(selectedIdsByCluster[kind] || []).length">
                已选 {{ (selectedIdsByCluster[kind] || []).length }} 人 · 黑线 = 该簇内均值
              </template>
              <span v-else class="caption-empty">本簇暂无选中</span>
            </p>
            <p
              v-if="(selectedIdsByCluster[kind] || []).length"
              class="caption-line caption-line--ids"
              :title="formatIdList(selectedIdsByCluster[kind] || [])"
            >
              {{ formatIdList(selectedIdsByCluster[kind] || []) }}
            </p>
          </div>
        </div>
      </div>
      <div class="labels">
        <div class="portrait-side-card portrait-side-card--knowledge">
          <div class="portrait-side-heading">Mastery of knowledge</div>
          <p class="portrait-side-note">外环为知识点维度（非学号）</p>
          <div id="label-bar" class="portrait-side-chart"></div>
        </div>
        <div class="portrait-side-card portrait-side-card--radar">
          <div class="portrait-side-heading">能力维度</div>
          <div id="label-radar" class="portrait-side-chart"></div>
        </div>
        <ul class="portrait-side-legend">
          <li><span class="portrait-legend-line portrait-legend-line--color"></span>彩色填充：簇代表学生（每簇 1 人）</li>
          <li><span class="portrait-legend-line portrait-legend-line--black"></span>黑色实线：你的选中在该簇的均值</li>
          <li><span class="portrait-legend-line portrait-legend-line--gray"></span>灰色虚线：背景网格</li>
        </ul>
      </div>
    </div>
  </div>
</template>

<script>
import { mapState, mapGetters, mapActions } from 'vuex'
import { getClusterStudents } from '@/api/PortraitView'
import LoadingSpinner from './LoadingSpinner.vue'

export default {
  name: 'PortraitView',
  components:{
    LoadingSpinner,
  },
  data() {
    return {
      debugger: true,
      loading: false,
      PortraitData: {},
      arc: null,
      radarLine: null,
      ourGroup: [null, null, null],
      hadRender: [false, false, false],
      _resizeObs: null,
      _resizeTimer: null,
      CAPTION_BLOCK_H: 58,
      CHART_SIZE_MIN: 260,
      CHART_SIZE_MAX: 380,
      radar_dimension: [
          'Error-Free Bonus', 
          'Test-Free Bonus',
          'Score',
          'Explore', 
          'Mem Bonus', 
          'TC Bonus', 
          'Rank',
          'Enthusiasm', 
        ] //便于控制指标渲染顺序
    }
  },
  created() {
    this.hadRender = [false, false, false]
  },
  async mounted() {
    await this.getPortraitData()
    await this.$nextTick()
    if (Object.keys(this.PortraitData).length > 0) {
      this.initialChart()
    }
    this.bindResize()
  },
  beforeUnmount() {
    if (this._resizeObs) {
      this._resizeObs.disconnect()
      this._resizeObs = null
    }
    if (this._resizeTimer) {
      clearTimeout(this._resizeTimer)
      this._resizeTimer = null
    }
  },
  computed: {
    ...mapState(['configLoaded']),
    ...mapGetters(['getSelectedData', 'getSelectedIds', 'getColors']),
    clusterKinds() {
      return [0, 1, 2]
    },
    clusterCenterByKind() {
      const map = { 0: '', 1: '', 2: '' }
      Object.entries(this.PortraitData || {}).forEach(([id, d]) => {
        if (d && d.cluster != null) map[d.cluster] = id
      })
      return map
    },
    selectedIdsByCluster() {
      const by = { 0: [], 1: [], 2: [] }
      const sel = this.getSelectedData || {}
      Object.entries(sel).forEach(([id, d]) => {
        const c = d?.cluster
        if (c === 0 || c === 1 || c === 2) by[c].push(id)
      })
      return by
    },
    selectionSummary() {
      const ids = this.getSelectedIds || []
      if (!ids.length) return ''
      const parts = [0, 1, 2]
        .map(k => {
          const n = this.selectedIdsByCluster[k].length
          return n ? `簇${k}×${n}` : null
        })
        .filter(Boolean)
      return `已选 ${ids.length} 人${parts.length ? `（${parts.join('，')}）` : ''}；彩色=簇代表，黑线=选中均值`
    },
  },
  methods: {
    ...mapActions(['toggleSelection']),
    shortId(id) {
      if (!id) return ''
      const s = String(id)
      return s.length > 8 ? s.slice(-5) : s
    },
    formatIdList(ids) {
      return (ids || []).map(id => this.shortId(id)).join(' · ')
    },
    formatKnowledgeLabel(name) {
      const s = String(name || '').trim()
      if (!s) return ''
      return s.length > 10 ? `${s.slice(0, 8)}…` : s
    },
    knowledgeLabelFontSize(count) {
      const n = count || 0
      if (n > 18) return '6px'
      if (n > 14) return '7px'
      return '8px'
    },
    async getPortraitData() {
      try {
        const response = await getClusterStudents();
        if (response && response.data) {
          this.PortraitData = response.data;
        } else {
          console.error('Unexpected response structure:', response);
          this.PortraitData = {}; // 或者设置为默认值
        }
      } catch (error) {
        console.error('Failed to fetch cluster students:', error);
        this.PortraitData = {}; // 或者设置为默认值
      }
    },
    async initialChart(){
      if (Object.keys(this.PortraitData).length === 0) return
      await this.$nextTick()
      this.renderPortraitData()
      await this.$nextTick()
      this.renderLabelBar()
      this.renderLabelRadar()
      if (this.getSelectedData && Object.keys(this.getSelectedData).length > 0) {
        this.renderSelectedData()
      }
    },
    bindResize() {
      const root = this.$el
      if (!root || typeof ResizeObserver === 'undefined') return
      this._resizeObs = new ResizeObserver(() => {
        if (this._resizeTimer) clearTimeout(this._resizeTimer)
        this._resizeTimer = setTimeout(() => this.reflowCharts(), 150)
      })
      this._resizeObs.observe(root)
    },
    reflowCharts() {
      if (!Object.keys(this.PortraitData).length) return
      this.renderPortraitData()
      this.renderLabelBar()
      this.renderLabelRadar()
      if (this.getSelectedData && Object.keys(this.getSelectedData).length > 0) {
        this.renderSelectedData()
      }
    },
    measureChartSize(kind) {
      const el = document.getElementById(`visualization${kind}`)
      const slot = el?.closest('.portrait-cluster-slot')
      if (!slot) return 300
      const rect = slot.getBoundingClientRect()
      const w = Math.max(rect.width - 12, this.CHART_SIZE_MIN)
      const h = Math.max(rect.height - this.CAPTION_BLOCK_H - 8, this.CHART_SIZE_MIN)
      return Math.max(
        this.CHART_SIZE_MIN,
        Math.min(this.CHART_SIZE_MAX, Math.floor(Math.min(w, h))),
      )
    },
    measureSideChartBox(selector, fallbackH) {
      const box = this.$el?.querySelector(selector)
      if (!box) return { width: 220, height: fallbackH }
      const rect = box.getBoundingClientRect()
      return {
        width: Math.max(Math.floor(rect.width) || 220, 180),
        height: Math.max(Math.floor(rect.height) || fallbackH, 120),
      }
    },
    renderPortraitData() {
      const d3 = this.$d3
      const useData = Object.values(this.PortraitData)
      useData.forEach((clusterData) => {
        const data = clusterData
        const kind = clusterData.cluster
        d3.select(`#visualization${kind}`).selectAll('*').remove()
        const knowledge_dimension = Object.keys(data.knowledge)
        const knowledge_data = Object.entries(data.knowledge).map(d => ({
          knowledge: d[0],
          value: d[1],
          index: d[1],
        }))
      
        const radar_dimension = this.radar_dimension
        const radar_data = radar_dimension.map(feature => ({
          features: feature,
          value: data.bonus[feature],
          index: data.bonus[feature],
        }))
      
        const size = this.measureChartSize(kind)
        const height = size
        const width = size
        const radius = Math.min(height, width) / 2
        const innerRadius = 0.5 * radius
        const outerRadius = radius
      
        const g = this.createSVGAndGroup(kind, height, width)
        const angleCircularBar = d3.scaleBand()
              .domain(knowledge_dimension)
              .range([0, 2 * Math.PI])
              .align(0)
        const radiusY = d3.scaleLinear()
              .domain([0, 1])
              .range([innerRadius, outerRadius])
        this.arc = d3.arc()
        .innerRadius(innerRadius)
        .outerRadius(d => radiusY(d.value))
        .startAngle(d => angleCircularBar(d.knowledge))
        .endAngle(d => angleCircularBar(d.knowledge) + angleCircularBar.bandwidth())
        .padAngle(0.02)
        .padRadius(innerRadius)
        
        // 绘制圆形虚线、直虚线
        this.drawCircularGrid(g, radius)
        this.drawCircularAxes(g, angleCircularBar, radiusY)
        // 绘制圆环柱状图
        this.drawCircularBars(g, knowledge_data, kind, true)
      
        const angleRadar = d3.scaleBand()
              .domain(radar_dimension)
              .range([0, 2 * Math.PI])
              .align(0)
  
        const radiusR = d3.scaleLinear()
              .domain([0, 1])
              .range([0, innerRadius])
        this.radarLine = d3.lineRadial()
        .radius(d => radiusR(d.value))
        .angle(d => angleRadar(d.features))
        // 绘制雷达图
        this.drawRadarChart(g, radar_data, this.radarLine, kind, true)
      })
    },
    createSVGAndGroup(index, height, width) {
      const d3 = this.$d3;
      const center = { X: width / 2, Y: height / 2 }

      const svg = d3.select(`#visualization${index}`)
        .html('') // Clear previous content
        .append('svg')
        .attr('width', width)
        .attr('height', height)

      const g = svg.append('g')
        .attr('transform', `translate(${center.X}, ${center.Y})`)

      this.ourGroup[index] = g
      

      return g
    },
    drawCircularBars(g, knowledge_data, kind, fill) {
      g.selectAll('path')
        .data(knowledge_data)
        .join('path')
        .attr('stroke', fill ? 'none' : 'black')
        .attr('stroke-width', fill ? 2 : 3)
        .attr('fill', fill ? `${this.getColors[kind]}` : 'none')
        .attr('d', this.arc)
    },
    drawCircularGrid(g, radius) {
  const d3 = this.$d3
  const levels = 3
  const opcityCircles = 0.01
  const lradius = radius

  const axisGrid = g.append('g')
    .attr('class', 'axis-grid')

  axisGrid.selectAll('.levels')
    .data(d3.range(1, levels + 1).reverse())
    .join('circle')
    .attr('class', 'grid-circle')
    .attr('r', d => d * (lradius / levels))
    .style('fill', '#CDCDCD')
    .style('stroke', '#CDCDCD')
    .style('fill-opacity', opcityCircles)
    .style('stroke-dasharray', '4, 4')
    },
    drawCircularAxes(g, angleCircularBar, radiusY) {
  // const d3 = this.$d3;

  const axis = g.append('g')
    .attr('class', 'axis')

  axis.selectAll('.axis')
    .data(angleCircularBar.domain())
    .join('g')
    .attr('class', 'axis')
    .append('line')
    .attr('x1', 0)
    .attr('y1', 0)
    .attr('x2', d => radiusY(1) * Math.sin(angleCircularBar(d)))
    .attr('y2', d => -radiusY(1) * Math.cos(angleCircularBar(d)))
    .attr('class', 'line')
    .style('stroke', '#CDCDCD')
    .style('stroke-width', '1px')
    .style('stroke-dasharray', '4, 3')
    },
    drawRadarChart(g, radar_data, radarLine, kind, fill) {
      const gradientId = `gradient-${kind}`
    
      g.append('defs')
        .append('radialGradient')
        .attr('id', gradientId)
        .attr('cx', '50%')
        .attr('cy', '50%')
        .attr('r', '100%')
        .selectAll('stop')
        .data([
          { offset: '0%', color: 'white' },
          { offset: '100%', color: `${this.getColors[kind]}`, opcityCircles: 0.8 },
        ])
        .enter().append('stop')
        .attr('offset', d => d.offset)
        .attr('stop-color', d => d.color)
        .attr('stop-opacity', d => d.opcityCircles);
      // 确保雷达图路径闭合
      const closedData = [...radar_data, radar_data[0]];
      g.append('path')
        .datum(closedData)
        .attr('fill', fill ? `url(#${gradientId})` : 'none')
        .attr('fill-opacity', fill ? 0.5 : 1)
        .attr('stroke', fill ? `${this.getColors[kind]}` : 'black')
        .attr('stroke-width', fill ? 2 : 2.5)
        .attr('d', radarLine)
    },
    renderLabelBar() {
      const d3 = this.$d3
      const { width, height } = this.measureSideChartBox('.portrait-side-card--knowledge .portrait-side-chart', 130)
      const cx = width / 2
      const cy = height / 2 + 6
      const labelRadius = Math.min(width, height) * 0.34

      const svg = d3.select('#label-bar')
        .html('')
        .append('svg')
        .attr('width', width)
        .attr('height', height)
        .attr('viewBox', `0 0 ${width} ${height}`)

      const firstItem = Object.values(this.PortraitData)[0]
      if (!firstItem?.knowledge) return
      const knowledge_dimension = Object.keys(firstItem.knowledge)
      const knowledgeNum = knowledge_dimension.length
      const labelItems = knowledge_dimension.map((name, index) => ({ name, index }))
      const ringG = svg.append('g').attr('transform', `translate(${cx}, ${cy})`)

      const segmentArc = d3.arc()
        .innerRadius(labelRadius * 0.72)
        .outerRadius(labelRadius)
        .startAngle(d => d.index * 2 * Math.PI / knowledgeNum)
        .endAngle(d => (d.index + 1) * 2 * Math.PI / knowledgeNum)
        .padAngle(0.04)
        .padRadius(labelRadius * 0.72)

      ringG.selectAll('.knowledge-arc')
        .data(labelItems)
        .join('path')
        .attr('class', 'knowledge-arc')
        .attr('fill', '#b8b8b8')
        .attr('d', segmentArc)

      const textArc = d3.arc()
        .innerRadius(labelRadius * 0.88)
        .outerRadius(labelRadius * 1.22)
        .startAngle(d => d.index * 2 * Math.PI / knowledgeNum)
        .endAngle(d => (d.index + 1) * 2 * Math.PI / knowledgeNum)

      const fontSize = this.knowledgeLabelFontSize(knowledgeNum)
      ringG.selectAll('.knowledge-label')
        .data(labelItems)
        .join('text')
        .attr('class', 'knowledge-label')
        .attr('transform', d => {
          const [x, y] = textArc.centroid(d)
          return `translate(${x}, ${y})`
        })
        .attr('text-anchor', (d, i) => (i >= knowledgeNum / 2 ? 'end' : 'start'))
        .attr('dominant-baseline', 'middle')
        .attr('font-size', fontSize)
        .attr('fill', '#333')
        .text(d => this.formatKnowledgeLabel(d.name))
        .each(function (d) {
          const el = d3.select(this)
          el.select('title').remove()
          el.append('title').text(d.name)
        })
    },
    renderLabelRadar() {
      const d3 = this.$d3
      const { width, height } = this.measureSideChartBox('.portrait-side-card--radar .portrait-side-chart', 150)
      const labelRadius = Math.min(width, height) * 0.34
      const labelCenter = {
        X: width / 2,
        Y: height / 2,
      }
      const svg = d3.select('#label-radar')
        .html('') // Clear previous content
        .append('svg')
        .attr('width', width)
        .attr('height', height)
        .attr('viewBox', `0 0 ${width} ${height}`)
      const labelG = svg.append('g')
        .attr('class', 'label-radar')
        .attr('transform', `translate(${labelCenter.X}, ${labelCenter.Y})`)
      
      // let features_dimension = Object.keys(Object.values(this.PortraitData)[0].radar)
      // 调整渲染顺序
      const features_dimension = this.radar_dimension
      const levels = 2
      const opcityCircles = 0.01

      const angleX = d3.scaleBand()
          .domain(features_dimension)
          .range([0, 2 * Math.PI])
          .align(0)
      
      // 圆圈虚线
      labelG.selectAll('.level-radar')
        .data(d3.range(1, levels + 1).reverse())
        .join('circle')
        .attr('class', 'grid-circle')
        .attr('r', d => d * (labelRadius / levels))
        .style('fill', '#CDCDCD')
        .style('stroke', '#CDCDCD')
        .style('fill-opacity', opcityCircles)
        .style('stroke-dasharray', '9, 9')
      // 直虚线
      const axis = labelG.selectAll('.axis-radar')
        .data(features_dimension)
        .join('g')

      axis.append('line')
        .attr('class', 'radar-line')
        .attr('x1', 0)
        .attr('y1', 0)
        .attr('x2', d => labelRadius * Math.cos(angleX(d)))
        .attr('y2', d => - labelRadius * Math.sin(angleX(d)))
        .style('stroke', '#000')
        .style('stroke-width', '1px')
        
        labelG.selectAll('.label-radar')
        .data(features_dimension)
        .join('g')
        .append('text')
        .attr('transform', d => {
          const x = labelRadius * Math.sin(angleX(d))
          const y =  - labelRadius * Math.cos(angleX(d))
          return `translate(${x}, ${y})`
        })
        .attr('text-anchor', (d, i) => {
          const angle = (i / features_dimension.length) * 2 * Math.PI
          if (angle === 0 || angle ===  Math.PI) return 'middle'
          if (angle < Math.PI || angle > 2 * Math.PI) return 'start'
          else return 'end'
        })
        .attr('font-size', '9px')
        .attr('fill', '#444')
        .text((d) => d)
    },
    renderSelectedData() {
      // const d3 = this.$d3

      const selectedData = this.getSelectedData
      // 分别渲染三种类型数据平均值
      for (let kind = 0; kind < 3; kind++) {
        // 筛选出i类数据
        const data = Object.values(selectedData).filter(d => d.cluster === kind)
        // 如果没有，则不渲染
        
        if (data.length === 0) {
          continue
        }
        // 计算当前类中所有学生的指标平均值
        const calculateAverage = (datum) => {
          // 初始化平均值对象
          const avgBonus = {}
          const avgKnowledge = {}

            // 初始化各项指标的总和
            this.radar_dimension.forEach(feature => {
            avgBonus[feature] = 0;
          })
          Object.keys(datum[0].knowledge).forEach(knowledge => {
            avgKnowledge[knowledge] = 0;
          })

          // 计算各项指标的总和
          datum.forEach(item => {
            this.radar_dimension.forEach(feature => {
              avgBonus[feature] += item.bonus[feature];
            })

            Object.keys(item.knowledge).forEach(knowledge => {
              avgKnowledge[knowledge] += item.knowledge[knowledge];
            })
          })

          // 计算平均值
          this.radar_dimension.forEach(feature => {
            avgBonus[feature] /= datum.length;
          })

          Object.keys(avgKnowledge).forEach(knowledge => {
            avgKnowledge[knowledge] /= datum.length;
          })
          return { avgBonus, avgKnowledge }
        }// function: calculateAverage
        const { avgBonus, avgKnowledge } = calculateAverage(data)

        // console.log(`Cluster ${kind} Average Bonus:`, avgBonus)
        // console.log(`Cluster ${kind} Average Knowledge:`, avgKnowledge)
        
        if (!this.ourGroup[kind]) continue
        let thisGroup = null
        if (this.ourGroup[kind].select('.select-group')) {
          this.ourGroup[kind].select('.select-group').remove()
        }
        thisGroup = this.ourGroup[kind].append('g')
            .attr('class', 'select-group')
          // this.ourGroup[kind].select('.select-group').clear()
        // 绘制圆环柱状图
        const knowledge_data = Object.entries(avgKnowledge).map(d => ({
          knowledge: d[0],
          value: d[1],
          index: d[1],
        }))
        this.drawCircularBars(thisGroup, knowledge_data, kind, false)
        // 绘制雷达图
        const radar_dimension = this.radar_dimension
        const radar_data = radar_dimension.map(feature => ({
          features: feature,
          value: avgBonus[feature],
          index: avgBonus[feature],
        }))
        this.drawRadarChart(thisGroup, radar_data, this.radarLine, kind, false)
        
        // 渲染逻辑
      } // for-i
    },
    async loadData() {
      this.loading = true
      this.$d3.select('.vis-panel').selectAll('svg').remove()
      
      this.PortraitData = {}
      this.arc =  null
      this.ourGroup = [null, null, null]
      this.hadRender = [false, false, false]

      await this.getPortraitData()
      await this.$nextTick()
      await this.initialChart()
      this.loading = false
    }
    
  },
  watch: {
    configLoaded(newVal) {
      if (newVal && this.debugger) {
        // 重新加载逻辑
        this.loadData()
      }
    },
    getSelectedData(newVal) {
      if (!newVal) {
        return
      }
      this.renderSelectedData()
    }
  },
}
</script>

<style scoped lang="less">
#portrait-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
  box-sizing: border-box;

  .title {
    flex-shrink: 0;
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 8px 12px;
    border-bottom: 1px solid #ddd;
    padding: 6px 12px;
  }

  .portrait-title-text {
    font-size: 17px;
    font-weight: 700;
    color: #222;
  }

  .portrait-summary-chip {
    flex: 1;
    min-width: 0;
    font-size: 11px;
    font-weight: normal;
    color: #555;
    line-height: 1.3;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .vis-container {
    flex: 1;
    min-height: 0;
    display: flex;
    align-items: stretch;
    gap: 8px;
    padding: 6px 8px 8px;
    box-sizing: border-box;
  }

  .vis-panel {
    position: relative;
    flex: 1;
    min-width: 0;
    min-height: 0;
    height: 100%;
    display: flex;
    align-items: stretch;
    justify-content: space-between;
    box-shadow: 0 0 10px rgba(0, 0, 0, 0.08);
    background: #fff;
    padding: 0;
    box-sizing: border-box;
  }

  .portrait-cluster-slot {
    flex: 1;
    min-width: 0;
    min-height: 0;
    height: 100%;
    display: grid;
    grid-template-rows: 1fr auto;
    align-items: stretch;
    border-right: 1px solid #eef1f5;
    box-sizing: border-box;

    &:last-child {
      border-right: none;
    }
  }

  .portrait-cluster-chart {
    min-height: 0;
    width: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
    overflow: hidden;
    padding: 4px 2px 0;
    box-sizing: border-box;
  }

  .portrait-viz-host {
    width: 100%;
    height: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
    line-height: 0;

    :deep(svg) {
      display: block;
      max-width: 100%;
      max-height: 100%;
    }
  }

  .portrait-cluster-caption {
    flex-shrink: 0;
    width: 100%;
    min-height: 58px;
    padding: 6px 10px 8px;
    background: #f6f8fa;
    border-top: 1px solid #e8ecf0;
    box-sizing: border-box;
    text-align: left;
  }

  .caption-line {
    margin: 0 0 3px;

    &:last-child {
      margin-bottom: 0;
    }
  }

  .caption-line--rep {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 4px 6px;
    font-size: 12px;
    color: #222;
  }

  .caption-line--stat {
    font-size: 11px;
    color: #555;
    line-height: 1.35;
  }

  .caption-line--ids {
    font-size: 10px;
    line-height: 1.35;
    color: #444;
    font-family: ui-monospace, Consolas, monospace;
    overflow: hidden;
    text-overflow: ellipsis;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    word-break: break-all;
  }

  .caption-tag {
    color: #fff;
    font-size: 11px;
    font-weight: 700;
    padding: 2px 7px;
    border-radius: 3px;
    line-height: 1.2;
  }

  .caption-rep-label {
    color: #777;
    font-size: 11px;
  }

  .caption-id {
    font-weight: 600;
    font-family: ui-monospace, Consolas, monospace;
    font-size: 12px;
    color: #111;
  }

  .caption-empty {
    color: #aaa;
    font-style: italic;
  }

  .labels {
    width: 236px;
    flex-shrink: 0;
    height: 100%;
    min-height: 0;
    display: grid;
    grid-template-rows: auto 1fr auto;
    gap: 6px;
    padding: 0 0 4px;
    box-sizing: border-box;
  }

  .portrait-side-card {
    min-height: 0;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    background: #fafbfc;
    border: 1px solid #e8ecf0;
    border-radius: 4px;
    padding: 6px 8px 4px;
    box-sizing: border-box;

    &--knowledge {
      flex: 0 0 auto;
      min-height: 148px;
    }

    &--knowledge .portrait-side-chart {
      min-height: 118px;
    }

    &--radar {
      min-height: 0;
    }
  }

  .portrait-side-heading {
    font-size: 11px;
    font-weight: 700;
    color: #333;
    line-height: 1.3;
    margin-bottom: 2px;
  }

  .portrait-side-note {
    margin: 0 0 4px;
    font-size: 10px;
    color: #888;
    line-height: 1.3;
  }

  .portrait-side-chart {
    flex: 1;
    min-height: 100px;
    width: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
    overflow: hidden;

    :deep(svg) {
      display: block;
      max-width: 100%;
      max-height: 100%;
    }
  }

  .portrait-side-card--radar .portrait-side-chart {
    min-height: 140px;
  }

  .portrait-side-legend {
    list-style: none;
    margin: 0;
    padding: 8px 10px;
    background: #fff;
    border: 1px solid #e8ecf0;
    border-radius: 4px;
    font-size: 11px;
    color: #333;
    line-height: 1.45;

    li {
      display: flex;
      align-items: flex-start;
      gap: 8px;
      margin-bottom: 6px;

      &:last-child {
        margin-bottom: 0;
      }
    }
  }

  .portrait-legend-line {
    flex-shrink: 0;
    width: 28px;
    height: 0;
    margin-top: 7px;
    border: none;

    &--color {
      border-top: 2px solid #888;
    }

    &--black {
      border-top: 2.5px solid #000;
    }

    &--gray {
      border-top: 1px dashed #999;
    }
  }
}
</style>



<template>
  <div id="portrait-view">
    <div class="title">
      <span>Portrait View</span>
    </div>
    <div class="vis-container">
      <div class="vis-panel">
        <LoadingSpinner v-if="loading" />
        <div id="visualization0" ref="visualization0"></div>
        <div id="visualization1" ref="visualization1"></div>
        <div id="visualization2" ref="visualization2"></div>
      </div>
      <div class="labels">
        <div id="label-bar"></div>
        <div id="label-radar"></div>
        <div id="label-legend"></div>
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
    this.initialChart()
  },
  computed: {
    ...mapState(['configLoaded']),
    ...mapGetters(['getSelectedData', 'getColors']),
  },
  methods: {
    ...mapActions(['toggleSelection']),
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
    initialChart(){
      this.renderPortraitData()
      this.renderLabelBar()
      this.renderLabelRadar()
      this.renderLegend()
    },
    renderPortraitData() {
      const d3 = this.$d3
      let useData = Object.values(this.PortraitData)
      useData.forEach((clusterData) => {
        const data = clusterData
        const kind = clusterData.cluster
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
      
        const height = 360
        const width = 360
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
        .attr('width', height)
        .attr('height', width)
        .attr('transform', `translate(${20}, ${0})`)

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
     const height = 200
     const width = 270
    //  const boxHeight = 50
     const labelRadius = 55
     const labelCenter = { 
       X: width / 2,
       Y: height / 2
      }
     const svg = d3.select('#label-bar')
       .html('') // Clear previous content
       .append('svg')
       .attr('width', width)
       .attr('height', height)
       .attr('transform', `translate(${5},${0})`)
     const labelG = svg.append('g')
       .attr('class', 'label-bar')
       .attr('transform', `translate(${labelCenter.X}, ${labelCenter.Y})`)
    
     const str = ['Mastery', 'of', 'knowledge']
     labelG.selectAll('.label-bar')
       .data(str)
       .join('g')
       .append('text')
       .attr('font-size', '0.7em')
       .attr('text-anchor', 'middle')
       .attr('transform', (d, i) => `translate(0, ${(i - 1) * 12})`)
       .text(d => d)
    
     const knowledge_dimension = Object.keys(Object.values(this.PortraitData)[0].knowledge)

     const knowledgeNum = knowledge_dimension.length
     const labelData = knowledge_dimension.map((_, i) => ({ r1: labelRadius * 0.8, r2: labelRadius, index: i }))
    
     const labelArc = d3.arc()
       .innerRadius(d => d.r1)
       .outerRadius(d => d.r2)
       .startAngle(d => d.index * 2 * Math.PI / knowledgeNum)
       .endAngle(d => (1 + d.index) * 2 * Math.PI / knowledgeNum)
       .padAngle(0.04)
       .padRadius(labelRadius * 0.8)
    
     labelG.selectAll('.label-bar')
       .data(labelData)
       .join('g')
       .append('path')
       .attr('fill', '#939393')
       .attr('d', labelArc)
    
     labelG.selectAll('.label-bar')
       .data(knowledge_dimension)
       .join('g')
       .append('text')
       .attr('transform', d => `translate(${labelArc.centroid({ r1: labelRadius, r2: labelRadius * 1.2, index: knowledge_dimension.indexOf(d) })})`)
       .attr('text-anchor', (d, i) => i >= knowledgeNum / 2 ? 'end' : 'start')
       .attr('font-size', '0.6em')
       .text(d => d)
    },
    renderLabelRadar() {
      const d3 = this.$d3
      const height = 200
      const width = 270
      // const boxHeight = 50
      const labelRadius = 55
      const labelCenter = { 
        X: width / 2,
        Y: height / 2 
      }
      const svg = d3.select('#label-radar')
        .html('') // Clear previous content
        .append('svg')
        .attr('width', width)
        .attr('height', height)
        .attr('transform', `translate(${5},${0})`)
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
        .attr('font-size', '0.6em')
        .text((d) => d )
    },
    renderLegend() {
      const d3 = this.$d3
      const height = 100
      const width = 200
      const boxHeight = 50
      const svg = d3.select('#label-legend')
        .html('') // Clear previous content
        .append('svg')
        .attr('width', width)
        .attr('height', height)
        .attr('transform', `translate(${20},${boxHeight - height / 2})`)
      
      // Create legend items
      const legendItems = [
        { text: 'features for cluster', lineStyle: 'solid' },
        { text: 'features', lineStyle: 'dashed' }
      ]

      legendItems.forEach((item, index) => {
        const y = index * 20 + 10
        svg.append('line')
          .attr('x1', 0)
          .attr('y1', y)
          .attr('x2', 80)
          .attr('y2', y)
          .style('stroke', 'black')
          .style('stroke-width', 1)
          .style('stroke-dasharray', item.lineStyle === 'dashed' ? '4, 4' : '')
        
        svg.append('text')
          .attr('x', 90)
          .attr('y', y + 5)
          .text(item.text)
          .style('font-size', '0.6em')
          .style('text-anchor', 'start')
      })
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
        console.log(data)
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
        
        let thisGroup = null
        if(this.ourGroup[kind].select('.select-group')){
          this.ourGroup[kind].select('.select-group').remove()
        }
        thisGroup =this.ourGroup[kind].append('g')
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
      this.initialChart()
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
  .title {
    border-bottom: 1px solid #ccc;
    padding-left: 20px;
    padding-top: 10px;
    padding-bottom: 5px;
    margin-bottom: 5px;
    span {
      font-size: 20px;
      font-weight: bold;
    }
  }

  .vis-container {
    height: 480px;
    width: 100%;
    margin-left: 10px;
    display: flex;
    justify-content: space-between;
    margin-top: 25px;
    .vis-panel {
      position: relative;
      width: 100%;
      display: flex;
      justify-content: space-between;
      margin-left: 0px;
      box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
  
      [id^='visualization'] {
        flex: 1;
        padding-top: 55px;
        display: inline-block;
      }
    }

    .labels {
      width: 300px;
      margin: 30px 0;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      align-items: center;
  
      #label-bar,
      #label-radar,
      #label-legend {
        width: 100%;
        height: calc(100% / 3);
        margin-top: 35px;
        display: flex;
        justify-content: center;
        align-items: center;
      }
    }
  }
}
</style>



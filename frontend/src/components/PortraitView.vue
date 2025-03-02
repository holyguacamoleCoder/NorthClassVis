<template>
  <div id="portrait-view" style="display: flex; justify-content: space-around;">
    <div class="title">
      <span>Portrait View</span>
    </div>
    <div class="vis-panel">
      <div id="visualization0"></div>
      <div id="visualization1"></div>
      <div id="visualization2"></div>
    </div>
    <div class="labels">
      <div id="label-bar"></div>
      <div id="label-radar"></div>
      <div id="label-legend"></div>
    </div>
  </div>
</template>

<script>
import { mapGetters, mapActions } from 'vuex'
import { getClusterStudents } from '@/api/PortraitView'
// import mockData from '@/mock/mockData.json'

export default {
  name: 'PortraitView',
  data() {
    return {
      PortraitData: [],
      ourGroup: [],
      arc: null,
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
    // this.PortraitData = mockData
  },
  async mounted() {
    // await this.getPortraitData()
  
  },
  computed: {
    ...mapGetters(['getSelection', 'getSelectionData', 'getColors', 'getHadFilter']),
    filteredSelectionData() {
      if (this.getSelectionData.length < 3) return []
      let useData = []
      for (let i = 0; i < this.getSelectionData.length; i++) {
        useData.push(this.getSelectionData[i])
      }
      return useData
    },
  },
  methods: {
    ...mapActions(['toggleSelection']),
    async getPortraitData() {
      // console.log('getPortraitData')
      const { data } = await getClusterStudents()
      this.PortraitData = data
      
      // this.renderPortraitData()
      this.renderLabelBar()
      this.renderLabelRadar()
      this.renderLegend()
    },
    async renderPortraitData() {
      const d3 = this.$d3
      let useData = Object.values(this.PortraitData)
      useData.forEach((clusterData, i) => {
        const data = clusterData
        const kind = clusterData.cluster
        const knowledge_dimension = Object.keys(data.knowledge)
        const knowledge_data = Object.entries(data.knowledge).map(d => ({
          knowledge: d[0],
          value: d[1],
          index: d[1],
        }))
        // let radar_dimension = Object.keys(data.radar)
        // let radar_data = Object.entries(data.radar).map(d => ({
        //   features: d[0],
        //   value: d[1],
        //   index: d[1],
        // }))
        const radar_dimension = this.radar_dimension
        const radar_data = radar_dimension.map(feature => ({
          features: feature,
          value: data.radar[feature],
          index: data.radar[feature],
        }))
        
        const height = 360
        const width = 360
        const radius = Math.min(height, width) / 2
        const innerRadius = 0.5 * radius
        const outerRadius = radius
        const center = { X: width / 2, Y: height / 2 }
        const svg = d3.select(`#visualization${i}`)
          .html('') // Clear previous content
          .append('svg')
          .attr('width', height)
          .attr('height', width)
          .attr('transform', `translate(${20}, ${0})`)
        const g = svg.append('g')
          .attr('transform', `translate(${center.X}, ${center.Y})`)
        this.ourGroup[i] = g
        
        
        const angleCircularBar = d3.scaleBand()
          .domain(knowledge_dimension)
          .range([0, 2 * Math.PI])
          .align(0)
      
        const radiusY = d3.scaleLinear()
          .domain([0, 1])
          .range([innerRadius, outerRadius])
        // 聚类柱状图
        this.arc = d3.arc()
          .innerRadius(innerRadius)
          .outerRadius(d => radiusY(d.value))
          .startAngle(d => angleCircularBar(d.knowledge))
          .endAngle(d => angleCircularBar(d.knowledge) + angleCircularBar.bandwidth())
          .padAngle(0.01)
          .padRadius(innerRadius)
      
        const levels = 3
        const opcityCircles = 0.01
        const lradius = radius
        const axisGrid = g.append('g')
          .attr('class', 'axis-grid')
        // 圆圈虚线
        axisGrid.selectAll('.levels')
          .data(d3.range(1, levels + 1).reverse())
          .join('circle')
          .attr('class', 'grid-circle')
          .attr('r', d => d * (lradius / levels))
          .style('fill', '#CDCDCD')
          .style('stroke', '#CDCDCD')
          .style('fill-opacity', opcityCircles)
          .style('filter', 'url(#glow)')
          .style('stroke-dasharray', '4, 4')
      
        // const knowledge = Object.keys(this.PortraitData[0].knowledge)
        const axis = axisGrid.selectAll('.axis')
          .data(knowledge_dimension)
          .join('g')
          .attr('class', 'axis')
        // 直虚线
        axis.append('line')
          .attr('x1', 0)
          .attr('y1', 0)
          .attr('x2', d => radiusY(1) * Math.sin(angleCircularBar(d)))
          .attr('y2', d => -radiusY(1) * Math.cos(angleCircularBar(d)))
          .attr('class', 'line')
          .style('stroke', '#CDCDCD')
          .style('stroke-width', '1px')
          .style('stroke-dasharray', '4, 3')
      
        // 绘制聚类柱状图
        g.selectAll('path')
          .data(knowledge_data)
          .join('path')
          .attr('fill', `${this.getColors[kind]}`)
          .attr('d', this.arc)

        // 绘制内圈雷达图
        const angleRadar = d3.scaleBand()
          .domain(radar_dimension)
          .range([0, 2 * Math.PI])
          .align(0)
        const radiusR = d3.scaleLinear()
          .domain([0, 1])
          .range([0, innerRadius])
        const radarLine = d3.lineRadial()
          .radius(d => radiusR(d.value))
          .angle(d => angleRadar(d.features))

        // 创建渐变
        const gradientId = `gradient-${kind}`
        svg.append('defs')
          .append('radialGradient')
          .attr('id', gradientId)
          .attr('cx', '50%')
          .attr('cy', '50%')
          .attr('r', '100%')
          .selectAll('stop')
          .data([
            { offset: '0%', color: 'white' },
            { offset: '100%', color: `${this.getColors[kind]}` , opcityCircles: 0.8},
            // { offset: '100%', color: `${this.getColors[kind]}`, opcityCircles: 0.8}
          ])
          .enter().append('stop')
          .attr('offset', d => d.offset)
          .attr('stop-color', d => d.color)
          .attr('stop-opacity', d => d.opcityCircles)
        // 确保雷达图路径闭合
        
        const closedData = [...radar_data, radar_data[0]]
        g.append('path')
          .datum(closedData)
          .attr('fill',  `url(#${gradientId})`)
          .attr('fill-opacity', 0.5)
          .attr('stroke', `${this.getColors[kind]}`)
          .attr('stroke-width', 2)
          .attr('d', radarLine)
          })
    },
    renderLabelBar() {
     const d3 = this.$d3
     const height = 200
     const width = 270
     const boxHeight = 50
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
       .attr('transform', `translate(${5},${boxHeight - height / 2})`)
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
      const boxHeight = 50
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
        .attr('transform', `translate(${5},${boxHeight - height / 2})`)
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
        .style('filter', 'url(#glow)')
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
        .attr('transform', `translate(${60},${boxHeight - height / 2})`)
      
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
    renderSelectData() {
      if (this.filteredSelectionData.length === 0) return

      this.filteredSelectionData.forEach(baseData => {
        const data = Object.entries(baseData.knowledge).map(d => ({
          knowledge: d[0],
          value: d[1],
          index: d[1],
        }))
        const kind = baseData.cluster
        if (this.hadRender[kind]) {
          this.ourGroup[kind].selectAll('.stu').remove()
        }
        this.ourGroup[kind]
          .append('g')
          .selectAll('path')
          .data(data)
          .join('g')
          .append('path')
          .attr('class', 'stu')
          .attr('fill', 'none')
          .attr('d', this.arc)
          .attr('stroke', 'black')
          .attr('stroke-width', '2px')
        this.hadRender[kind] = true
      })
    },
    
  },
  watch: {
    getSelection: {
      handler() {
        this.renderSelectData()
      },
      deep: true,
    },
    getHadFilter() {
      console.log('had filter change!!')
      this.$d3.select('#visualization0').selectAll('*').remove()
      this.$d3.select('#visualization1').selectAll('*').remove()
      this.$d3.select('#visualization2').selectAll('*').remove()
      this.$d3.select('#label-bar').selectAll('*').remove()
      this.getPortraitData()
    },
  },
}
</script>

<style scoped lang="less">
#portrait-view {
  position: relative;
  .title{
    border-bottom: 1px solid #ccc; 
    width: 100%;
    padding-left: 20px;
    padding-top: 10px;
    padding-bottom: 5px;
    margin-bottom: 5px;
    span{
      font-size: 20px;
      font-weight: bold;
    }
  }
  @visPanelWidth: 1210px;
  .vis-panel {
    position: absolute;
    top: 45px;
    height: 480px;
    left: 10px;
    width: @visPanelWidth;
    margin-top: 25px;
    margin-left: 0px;
    box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);

    [id^='visualization'] {
      width: calc(@visPanelWidth / 3);
      padding-top: 55px;
      display: inline-block;
    }
  }
  @labelsHeight: 500px;
  @labelWidth: 90px;
  .labels {
    height: @labelsHeight;
    width: @labelWidth;
    z-index: 5;
    top: 100px;
    right: 165px;
    position: absolute;
    margin: 30px 0;
    //background-color: blue;
    @labelHeight: calc(@labelsHeight / 3);
    #label-bar {
      height: @labelHeight;
      width: @labelWidth;
      //background-color: red;
    }

    #label-radar {
      height: @labelHeight;
      width: @labelWidth;
      //background-color: green;
    }
  }
}
</style>




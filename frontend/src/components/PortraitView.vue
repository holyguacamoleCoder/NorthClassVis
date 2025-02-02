<template>
  <div id="portrait-view" style="display: flex; justify-content: space-around;">
    <h3>Portrait View</h3>
    <!-- <span class="hint">hint: you can choose three kinds of students in ParallelView</span> -->
    <div class="vis-panel">
      <div id="visualization0"></div>
      <div id="visualization1"></div>
      <div id="visualization2"></div>
    </div>
    <div class="labels">
      <div id="label-bar"></div>
    </div>
  </div>
</template>

<script>
import { mapGetters } from 'vuex'
import { getClusters } from '@/api/PortraitView'
export default {
  name: 'PortraitView',
  data() {
    return {
      PortraitData: [],
      ourGroup: [],
      arc: null,
      hadRender: [],
    };
  },
  created(){
    this.hadRender = [false, false, false]
  },
  async mounted() {
    // this.getPortraitData()
  },
  computed:{
    ...mapGetters(['getSelection','getSelectionData', 'getColors','getHadFilter']),
    SelectionData(){
      return this.$store.state.getSelectionData
    },
  },
  methods: {
    async getPortraitData() {
      // 获取聚类中心数据
      console.log('getPortraitData')
      const { data } = await getClusters()
      this.PortraitData = data
      this.renderPortraitData()
      this.renderLabelBar()
    },
    renderPortraitData(){
      console.log('renderPortraitData')
      const d3 = this.$d3
      // const clusterData = this.PortraitData[0]
      let useData = []
      for (let i = 0; i < 3; i++) {
        useData.push(this.PortraitData[`${i}`])
      }
      console.log('useData:',useData)
      // console.log('color:',color)
      // 渲染三种类型
      useData.forEach((clusterData, i) => {
        const kind = clusterData.cluster
        const data = Object.entries(clusterData.knowledge).map((d, i) => {
          return {
            'knowledge': d[0], 
            'value': d[1], 
            'index': i
          }
        })
        const height = 375
        const width = 375
        const radius = Math.min(height, width) / 2
        const innerRadius = 0.3 * radius
        const outerRadius = 0.9 * radius
        const center ={X: width / 2, Y: height / 2}
        const svg = d3.select(`#visualization${i}`)
          .append('svg')
          .attr('width', height)
          .attr('height', width)
        const g = svg.append('g')
          .attr('transform', `translate(${center.X}, ${center.Y})`)
        this.ourGroup[i] = g 
        // console.log('g:',g)
        // 定义角度缩放尺
        const angleX = d3.scaleBand()
          .domain(data.map(d => d.knowledge))
          .range([0, 2 * Math.PI])
          .align(0)
        // 定义半径缩放尺
        const radiusY = d3.scaleLinear()
        .domain([0, 1])
        .range([innerRadius, outerRadius])
        // 定义曲线生成器
        this.arc = d3.arc()
            .innerRadius(innerRadius)
            .outerRadius(d => radiusY(d.value))
            .startAngle(d => angleX(d.knowledge))
            .endAngle(d => angleX(d.knowledge) + angleX.bandwidth())
            .padAngle(0.01)
            .padRadius(innerRadius)
        
        // -----renderLabelRadar-------
        const levels = 3
        const opcityCircles = 0.01
        const lradius = radius * 0.8
        const axisGrid = g.append('g')
          .attr('class', 'axis-grid')
        // 绘制背景圆圈
        axisGrid.selectAll('.levels')
          .data(d3.range(1, levels + 1).reverse())
          .enter()
            .append('circle')
            .attr('class', 'grid-circle')
            .attr('r', d => d * (lradius / levels))
            .style('fill', '#CDCDCD')
            .style('stroke', '#CDCDCD')
            .style('fill-opacity', opcityCircles)
            .style('filter', 'url(#glow)')
            .style('stroke-dasharray', '4, 4')
      
         // 文本标识每层分数
         // 绘制直线从中心射向外围
         const knowledge = Object.keys(this.PortraitData[0])
         const axis = axisGrid.selectAll('.axis')
            .data(knowledge)
            .enter()
            .append('g')
            .attr('class', 'axis')
         axis.append('line')
            .attr('x1', 0)
            .attr('y1', 0)
            .attr('x2', d => radiusY(0.8) * Math.sin(angleX(d)))
            .attr('y2', d => -radiusY(0.8) * Math.cos(angleX(d)))
            .attr('class', 'line')
            .style('stroke', '#CDCDCD')
            .style('stroke-width', '1px')
            .style('stroke-dasharray', '4, 3')
         // 绘制文本标签
         axis.append('text')        
                
        
        // 绘制每个知识点的柱状图
        g.append('g')
        .selectAll('path')
        .data(data)
        .join('g')
        .append('path')
          .attr('fill', `${this.getColors[kind]}`)
          .attr('d', this.arc)
          // .attr('stroke', 'black')
          // .attr('stroke-width', '2px')

            
      })// forEach-clusterData

      //-------- 渲染标签radar-bar图-----------
    },
    renderLabelBar(){
      const d3 = this.$d3
      const height = 165
      const width = height
      const labelRadius = Math.min(height, width) / 3
      const labelCenter ={X: width / 2, Y: height / 2}
      const svg = d3.select('#label-bar')
        .append('svg')
        .attr('width', height)
        .attr('height', width)
        .attr('transform', `translate(${5},${220 - height / 2})`)
      const labelG = svg.append('g')
        .attr('class', 'label-bar')
        .attr('transform', `translate(${labelCenter.X}, ${labelCenter.Y})`)
      const labelData = []
      const knowledge = Object.keys(this.PortraitData[0].knowledge)
      
      const str = ['Mastery', 'of', 'knowledge']
      labelG.selectAll('.label-bar')
      .data(str)
      .enter()
      .append('g')
      .append('text')
        .attr('font-size', '0.7em')
        .attr('text-anchor', 'middle')
        .attr('transform', (d, i) => `translate(0, ${(i - 1) * 12})`)
        .text(d => d)
      // .style('width', 50)
      // .style('height', 50)
      // .html(`<p>Mastery</p>
      //         <p>of</p> 
      //         <p>knowledge</p>`)

      // console.log('kno', knowledge)
      const knowledgeNum = knowledge.length
      for(let i = 0; i < knowledgeNum; i++){
        labelData.push({r1: labelRadius * 0.8, r2: labelRadius, index:i})
      }
      const labelArc = d3.arc()
        .innerRadius(d => d.r1)
        .outerRadius(d => d.r2)
        .startAngle(d => d.index * 2 * Math.PI / knowledgeNum)
        .endAngle(d => (1 + d.index) * 2 * Math.PI / knowledgeNum)
        .padAngle(0.04)
        .padRadius(labelRadius * 0.8)

      labelG.selectAll('.label-bar')
      .data(labelData)
      .enter()
      .append('g')
      .append('path')
        .attr('fill', '#939393')
        .attr('d', labelArc)
      // 为标签圆打上知识点
      labelG.selectAll('.label-bar')
      .data(knowledge)
      .enter()
      .append('g')
      .append('text')
        .attr('transform', d => `translate(${labelArc.centroid({r1: labelRadius * 0.8, r2: labelRadius, index:knowledge.indexOf(d)})})`)
        .attr('text-anchor', (d, i) => i > 3 ? 'end' : 'start')
        .attr('font-size', '0.7em')
        .text(d => d)
    },
    renderSelectData(){
      // console.log('len',this.getSelectionData.length)
      if(this.getSelectionData.length < 3) return
      
      // 只渲染筛选的三类

      let useData = []
      for (let i = 0; i < this.getSelectionData.length; i++) {
        useData.push(this.getSelectionData[`${i}`])
      }
      useData.forEach(baseData => {
        console.log('bd', baseData)
        const data = Object.entries(baseData.knowledge).map((d, i) => {
          return {
            'knowledge': d[0], 
            'value': d[1], 
            'index': i
          }
        })
        // console.log('renderSelect', data)
        const kind = baseData.cluster
        if(this.hadRender[kind]) {
          // 如果这个类的图已经被渲染了，那先删除这个图上的元素
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
        // console.log(want)
        this.hadRender[kind] = true

        // this.ourGroup[kind].append('text')
        // .text('6666')
      })
    }
  },//method
  watch:{
    getSelection: {
      handler(){
        // console.log('chanaaaage!!', newVal, oldVal)
        this.renderSelectData()
      },
      deep:true
    },
    getHadFilter(){
      console.log('had filter change!!')
      this.$d3.select('#visualization0').selectAll('*').remove()
      this.$d3.select('#visualization1').selectAll('*').remove()
      this.$d3.select('#visualization2').selectAll('*').remove()
      this.$d3.select('#label-bar').selectAll('*').remove()
      this.getPortraitData()
    }
  }
};
</script>

<style scoped lang="less">
#portrait-view {
  width: 1290px;
  height: 585px;
  margin-left: 6px;
  position: relative;
  border-radius: 5px;
  background-color: #fff;
  h3{
    height: 20px;
    width: inherit;
    font-size: 20px;
    padding: 0 10px 10px;
    margin: 10px 5px;
    border-bottom: 1px solid #ccc;
  }
  .vis-panel{
    position: absolute;
    top: 45px;
    height: 450px;
    left: 0;
    width: 1100px;
    margin-top: 45px;
    margin-left: 8px;
    box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
    [id^='visualization']{
      width: 33%;
      padding-top: 55px;
      display: inline-block;
    }
  }
  .labels{
    height: 500px;
    width: 175px;
    z-index: 5;
    top: 42px;
    right: 0;
    position: absolute;
    margin: 10px 0;
    .label-bar{
      height: 240px;
      width: 240px;
      border: 1px solid #ccc;
    }
    .label-radar{
      height: 240px;
      width: 240px;
      border: 1px solid #ccc;
    }
  }
}
</style>

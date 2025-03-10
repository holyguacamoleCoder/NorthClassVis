<template>
  <div id="scatter-chart">
    <div class="title">
      <span>Scatter View</span>
      <button class="brush-button" @click="toggleBrush">
      </button>
      <!-- <button class="click-button" @click="toggleBrush"></button> -->
    </div>
    <div class="labels">
      <div class="label" v-for="(color, i) in getColors" :key="i">
        cluster{{i}}
        <div class="color-box" :style="{ backgroundColor: color }"></div>
      </div>
    </div>
    <div>
      <div id="visualizationS" ref="visualizationS">
        <LoadingSpinner v-if=loading />
      </div>
    </div>
  </div>
</template>

<script>
import { getScatterData } from '@/api/ScatterView'
import { mapState, mapActions, mapGetters } from 'vuex'
import LoadingSpinner from './LoadingSpinner.vue'
export default {
  name: 'ScatterView',
  data() {
    return {
      debugger: true,
      loading: false,
      svg: null,
      g: null,
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
      brushEnabled: false
    }
  },
  components: {
    LoadingSpinner
  },
  async mounted() {
    const { data } = await getScatterData()
    this.allData = data 
    this.initChart()
  },
  computed: {
    ...mapState(['configLoaded']),
    ...mapGetters(['getSelection', 'getColors', 'getHadFilter']),
 
  },
  methods: {
    ...mapActions(['fetchScatterData', 'toggleSelection']),
    updateChart(event){
      if (!event.selection) return
      function isBrushed(brush_coords, cx, cy) {
           var x0 = brush_coords[0][0],
               x1 = brush_coords[1][0],
               y0 = brush_coords[0][1],
               y1 = brush_coords[1][1];
          return x0 <= cx && cx <= x1 && y0 <= cy && cy <= y1;    // This return TRUE or FALSE depending on if the points is in the selected area
      }
      const extent = event.selection
      const circles = this.g.selectAll('.circle-scatter')
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
      this.updateCircles() // 立即更新圆点样式

    },
    async initChart() {
      const d3 = this.$d3
      const height = 450
      const width = 350
      const margin = { top: 30, right: 10, bottom: 10, left: 30 }

      // 初始化SVG和G元素
      this.svg = d3.select("#visualizationS")
          .append("svg")
          .attr("width", width)
          .attr("height", height)
      this.g = this.svg.append("g")
          .attr("transform", `translate(${margin.left},${margin.top})`)

      // 定义x轴和y轴比例尺
      this.xScale = d3.scaleLinear()
          .domain([-1, 1])
          .range([0, width - margin.right - margin.left])

      this.yScale = d3.scaleLinear()
          .domain([-1, 1])
          .range([height - margin.top - margin.bottom, margin.top])

      // 创建tooltip
      this.tooltip = d3.select('#visualizationS').append('div')
          .attr('class', 'tooltip')
          .style('position', 'absolute')
          .style('visibility', 'hidden') 
          .style('background-color', 'white')
          .style('border', '1px solid black')
          .style('padding', '5px')
          .style('z-index', 10)
      

      this.totalBatches = Math.ceil(this.allData.length / this.batchSize)
      this.renderNextBatch()

      // 绘制坐标轴
      // const xAxis = d3.axisBottom(this.xScale)
      // const yAxis = d3.axisLeft(this.yScale)
      
      this.g.append('g')
          .attr('transform', `translate(0,${height - margin.top - margin.bottom})`)
      
      this.brushing = d3.brush()
            .on("start", () => {
              console.log('start')
              this.brushedStudent.clear()
              console.log(this.brushedStudent.size)
            }) // 清空brushedStudent数
            .on("brush", this.updateChart.bind(this))
            .on("end", () => {            
              this.updateChart.bind(this)
              console.log(this.brushedStudent.size)
              this.$emit('brushed-students-updated', Array.from(this.brushedStudent))
            })
      // this.g.call(this.brushing)
      // this.updateBrushing()
    },
    renderNextBatch() {
      if (this.currentBatch >= this.totalBatches) return

      const start = this.currentBatch * this.batchSize
      const end = Math.min(start + this.batchSize, this.allData.length)
      const batchData = this.allData.slice(start, end)

      this.renderedData.push(...batchData) // 将当前批次的数据添加到渲染数据中

      // 使用 enter-update-exit 模式
      const circles = this.g.selectAll('.circle-scatter')
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
          // .classed('selected', d => this.brushedStudent.has(d.student_id))
          .on('click', (e, d) => {
            this.toggleSelection(d.student_id)
            this.updateCircles()
          })
          .on('mouseover', (e, d) => {
            this.tooltip.style('visibility', 'visible')
                .html(`student: ${d.student_id} <br>cluster: ${d.cluster}`)
                .style('left', `${e.pageX + 10}px`)
                .style('top', `${e.pageY + 10}px`)
          })
          .on('mouseout', () => {
            this.tooltip.style('visibility', 'hidden')
          })

      circles.exit().remove()

      this.currentBatch++
      setTimeout(() => this.renderNextBatch(), 0) // 使用setTimeout来模拟异步加载
      
      
    },
    updateCircles() {
      // 使用 enter-update-exit 模式
      const circles = this.g.selectAll('.circle-scatter')
          .data(this.renderedData, d => d.student_id)

      circles.enter().append('circle')
          .attr('class', 'circle-scatter')
          .merge(circles)
          .attr('cx', d => this.xScale(d.transform.x))
          .attr('cy', d => this.yScale(d.transform.y))
          .attr('r', 5)
          .attr('fill', d => this.getColors[d.cluster])
          .attr('stroke', d => this.clickedStudent.has(d.student_id) || this.brushedStudent.has(d.student_id) ? 'black' : 'none')
          .attr('stroke-width', d => this.clickedStudent.has(d.student_id) || this.brushedStudent.has(d.student_id) ? 1 : 0)
          .attr('opacity', d => this.clickedStudent.has(d.student_id) || this.brushedStudent.has(d.student_id) ? 1 : 0.8)
          .on('click', (e, d) => {
            if(this.clickedStudent.has(d.student_id)){
              this.clickedStudent.delete(d.student_id)
            }
            else this.clickedStudent.add(d.student_id)
            this.updateCircles()
          })
          .on('mouseover', (e, d) => {
            this.tooltip.style('visibility', 'visible')
                .html(`student: ${d.student_id} <br>cluster: ${d.cluster}`)
                .style('left', `${e.pageX + 10}px`)
                .style('top', `${e.pageY + 10}px`)
          })
          .on('mouseout', () => {
            this.tooltip.style('visibility', 'hidden')
          })

      circles.exit().remove()
    },
    updateBrushing() {
      if(this.brushEnabled === false) {
        this.g.call(this.brushing.move, null) // 清除当前的刷选区域
        this.g.on('.brush', null) // 移除所有brush事件
      }else{
        this.g.call(this.brushing)
      }
    },
    toggleBrush() {
      this.brushEnabled = !this.brushEnabled
      this.updateBrushing()
    },
    async loadData() {
      this.loading = true
      // this.svg.selectAll('*').remove()
      this.$d3.select('#visualizationS').selectAll('*').remove()
      const { data } = await getScatterData()
      this.svg = null
      this.g = null
      this.xScale = null
      this.yScale = null
      this.tooltip = null
      this.currentBatch = 0
      this.totalBatches = 0
      this.allData = []
      this.renderedData = []
      this.allData = data 
      this.initChart()
      this.loading = false
    },
  },
  watch: {
    configLoaded(newVal) {
      if (newVal) {
        // 重新加载逻辑
        this.loadData()
      }
    },
    async getHadFilter() {
      console.log('had filter change!!SSSS')
      this.svg.selectAll('*').remove()
      await this.fetchScatterData()
      this.initChart()
    },
    brushEnabled() {
      this.updateBrushing()
    }
  }
}
</script>


<style scoped lang="less">
#scatter-chart {
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
    .brush-button{
      float: right;
      position: relative;
      margin-top: 4px;
      margin-right: 40px;
      height: 20px;
      width: 20px;
      border: 0;
      background: no-repeat center/85% url('~@/assets/images/brush.png') ;
    }
    .click-button{
      float: right;
      position: relative;
      margin-top: 4px;
      margin-right: 10px;
      height: 20px;
      width: 20px;
      border: 0;
      background: no-repeat center/100% url('~@/assets/images/click.png') ;
    }
  }
  .labels{
    width: inherit;
    height: 20px;
    margin-left: 30px; 
    display: flex;
    align-items: center;
    flex-direction: row;
    justify-content: center;
    .label{
      flex: 1;
      margin-right: 10px;
      margin-top: 5px;
      position: relative;
      font-size:17px;
      .color-box{
        position: absolute;
        width: 10px;
        height: 10px;
        border-radius: 50%;
        background-color: #000;
        top: 6px;
        left: 67px;
      }
    }
  }
  #visualizationS {
    position: relative;
    margin: 20px;
    padding: 0 20px 20px 0;
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

</style>


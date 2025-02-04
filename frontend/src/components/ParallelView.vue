<template>
  <div id="scatter-chart">
    <div class="title">
      <span>Parallel View</span>
    </div>
    <div class="labels">
      <div class="label" v-for="(color, i) in getColors" :key="i">
        cluster{{i}}
        <div class="color-box" :style="{ backgroundColor: color }"></div>
      </div>
    </div>
    <div id="visualizationP"></div>
  </div>
</template>

<script>
import { mapActions, mapGetters } from 'vuex'

export default {
  name: 'ScatterView',
  data() {
    return {
      lines: null,
      svg: null,
      g: null,
      dimensionsX: null,
      scoreY: null,
      lineGenerator: null,
      yAxis: null,
      tooltip: null,
      batchSize: 100, // 每批加载的数据量
      currentBatch: 0, // 当前批次索引
      totalBatches: 0, // 总批次数
      allData: [], // 所有数据
      renderedData: [] // 已渲染的数据
    }
  },
  async mounted() {
    // this.initChart()
  },
  computed: {
    ...mapGetters(['getClusterData', 'getSelection', 'getColors', 'getHadFilter']),
  },
  methods: {
    ...mapActions(['fetchClusterData', 'toggleSelection']),
    initChart() {
      const startTime = performance.now(); // 记录开始时间

      const d3 = this.$d3
      const height = 450
      const width = 350
      const margin = { top: 30, right: 10, bottom: 10, left: 30 }

      // 初始化SVG和G元素
      this.svg = d3.select("#visualizationP")
          .append("svg")
          .attr("width", width)
          .attr("height", height)
      this.g = this.svg.append("g")
          .attr("transform", `translate(${margin.left},${margin.top})`)

     

      // 获取维度
      if (Object.keys(this.getClusterData).length === 0) {
        console.error('No cluster data available');
        return;
      }

      const dimensions = Object.keys(Object.values(this.getClusterData)[0].knowledge)
      this.dimensionsX = d3.scalePoint()
          .domain(dimensions)
          .range([0, width - margin.right - margin.left])

      // 定义分数线性比例尺
      this.scoreY = d3.scaleLinear()
          .domain([0, 1])
          .range([height - margin.top - margin.bottom, margin.top])

      // 定义线条生成器
      this.lineGenerator = d3.line()
          .x(d => this.dimensionsX(d.key))
          .y(d => this.scoreY(d.value))

      // 定义坐标轴
      this.yAxis = d3.axisLeft(this.scoreY)

      // 创建tooltip
      this.tooltip = d3.select('#visualizationP').append('div')
          .attr('class', 'tooltip')
          .style('position', 'absolute')
          .style('visibility', 'hidden') 
          .style('background-color', 'white')
          .style('border', '1px solid black')
          .style('padding', '5px')
          .style('z-index', 10)

      // 处理数据
      this.allData = Object.entries(this.getClusterData).map(([stu_id, info]) => ({
        stu_id,
        cluster: info.cluster,
        knowledge: info.knowledge
      })).map(d => ({
        stu_id: d.stu_id,
        cluster: d.cluster,
        values: Object.entries(d.knowledge).map(([key, value]) => ({ key, value }))
      }))

      this.totalBatches = Math.ceil(this.allData.length / this.batchSize)
      this.renderNextBatch()

      // 绘制坐标轴
      const yAxis = this.yAxis; // Save yAxis to a local variable

      this.g.selectAll('.axis')
          .data(dimensions)
          .enter()
          .append('g')
          .attr('class', 'axis')
          .attr('transform', d => `translate(${this.dimensionsX(d)},${0})`)
          .each(function() {
            d3.select(this).call(yAxis)
          })
          .append('text')
              .attr('y', -9)
              .style('text-anchor', 'middle')
              .text(d => d)
              .style('fill', 'black')

      const endTime = performance.now(); // 记录结束时间
      console.log(`ParallelView Render time: ${endTime - startTime} milliseconds`)
    },
    renderNextBatch() {
      if (this.currentBatch >= this.totalBatches) return

      const start = this.currentBatch * this.batchSize
      const end = Math.min(start + this.batchSize, this.allData.length)
      const batchData = this.allData.slice(start, end)

      this.renderedData.push(...batchData) // 将当前批次的数据添加到渲染数据中
                                           // 结合d3的增量渲染，提高效率

    

      // 使用 enter-update-exit 模式
      const lines = this.g.selectAll('.line-para')
          .data(this.renderedData, d => d.stu_id)

      lines.enter().append('path')
          .attr('class', 'line-para')
          .merge(lines)
          .attr('d', d => this.lineGenerator(d.values))
          .attr('fill', 'none')
          .attr('stroke', d => this.getColors[d.cluster])
          .attr('stroke-width', d => this.getSelection.includes(d.stu_id) ? 5 : 1.5)
          .attr('opacity', d => this.getSelection.includes(d.stu_id) ? 1 : 0.8)
          .on('click', (e, d) => {
            this.toggleSelection(d.stu_id)
            this.updateLines()
          })
          .on('mouseover', (e, d) => {
            this.tooltip.style('visibility', 'visible')
                .html(`student: ${d.stu_id} <br>cluster: ${d.cluster}`)
                .style('left', `${e.pageX + 10}px`)
                .style('top', `${e.pageY + 10}px`)
          })
          .on('mouseout', () => {
            this.tooltip.style('visibility', 'hidden')
          })

      lines.exit().remove()

      this.currentBatch++
      setTimeout(() => this.renderNextBatch(), 0) // 使用setTimeout来模拟异步加载
    },
    updateLines() {
      

      // 使用 enter-update-exit 模式
      const lines = this.g.selectAll('.line-para')
          .data(this.renderedData, d => d.stu_id)

      lines.enter().append('path')
          .attr('class', 'line-para')
          .merge(lines)
          .attr('d', d => this.lineGenerator(d.values))
          .attr('fill', 'none')
          .attr('stroke', d => this.getColors[d.cluster])
          .attr('stroke-width', d => this.getSelection.includes(d.stu_id) ? 5 : 1.5)
          .attr('opacity', d => this.getSelection.includes(d.stu_id) ? 1 : 0.8)
          .on('click', (e, d) => {
            this.toggleSelection(d.stu_id)
            this.updateLines()
          })
          .on('mouseover', (e, d) => {
            this.tooltip.style('visibility', 'visible')
                .html(`student: ${d.stu_id} <br>cluster: ${d.cluster}`)
                .style('left', `${e.pageX + 10}px`)
                .style('top', `${e.pageY + 10}px`)
          })
          .on('mouseout', () => {
            this.tooltip.style('visibility', 'hidden')
          })

      lines.exit().remove()
    },
    handleLineClick(d) {
      this.toggleSelection(d.stu_id)
    },
  },
  watch: {
    getSelection: {
      handler() {
        this.updateLines()
      },
      deep: true
    },
    async getHadFilter() {
      console.log('had filter change!!PPPP')
      this.svg.selectAll('*').remove()
      await this.fetchClusterData()
      this.initChart()
    }
  }
}
</script>

<style scoped lang="less">
#scatter-chart {
  width: 100%;
  height: 585px;
  border-radius: 5px;
  background-color: #fff;
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
  #visualizationP {
    border: 1px solid #ccc;
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




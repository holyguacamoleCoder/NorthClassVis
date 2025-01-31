<template>
  <div id="scatter-chart">
    <div class="title">
      <span>Parallel View</span>
    </div>
    <div class="labels">
      <div class="label" v-for="color, i in getColors" :key="color">
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
  data(){
    return {
      lines: null,
      // colors:['#ff7f00', '#377eb8', '#4daf4a']
    }
  },
  async mounted() {
    this.renderParallel()
  },
  computed: {
    ...mapGetters(['getClusterData', 'getSelection', 'getColors', 'getHadFilter']),
  },
  methods: {
    ...mapActions(['fetchClusterData', 'toggleSelection']),
    async renderParallel() {
      const d3 = this.$d3
      const data = []
      const midData = await Object.entries(this.getClusterData).map((d) => {
        return {
          'stu_id': d[0], 
          'cluster': d[1].cluster,
          'knowledge': d[1].knowledge
        }
      })
      midData.forEach((d) => {
        // console.log('d:', d)
        // data[i] = d
        data.push(d)
      })

      // 定义基础数据
      const height = 450
      const width = 350
      const margin = { top: 25, right: 10, bottom: 30, left: 30 }
      const svg = d3.select("#visualizationP")
          .append("svg")
          .attr("width", width)
          .attr("height", height)
      const g = svg.append("g")
          .attr("transform", "translate(" + margin.left + "," + margin.top + ")")
      // 定义颜色
      const color = this.getColors
      // 获取维度
      const dimensions = Object.keys(data[0].knowledge)
      // console.log('dimensions:', dimensions)
      // 定义 分数线性比例尺
      const scoreY = d3.scaleLinear()
          .domain([0, 1])
          .range([height - margin.top - margin.bottom, margin.top])
      // 定义 维度点比例尺
      const dimensionsX = d3.scalePoint()
          .domain(dimensions)
          .range([0, width - margin.right - margin.left])
      // 定义线条生成器
      const line = function(d){
        return d3.line()(
          dimensions.map(p => [dimensionsX(p), scoreY(d[p]) + margin.top])
        )
      } 
      // 定义坐标轴
      const yAxis = d3.axisLeft(scoreY)

      // 创建tooltip
      const tooltip = d3.select('#visualizationP').append('div')
        .attr('class', 'tooltip')
        .style('position', 'absolute')
        .style('visibility', 'hidden') 
        .style('background-color', 'white')
        .style('border', '1px solid black')
        .style('padding', '5px')
        .style('z-index', 10)
       // 绘制线
      this.lines = g.selectAll('.line-para')
      .data(data)
      .enter()
      .append('path')
      .attr('class', 'line-para')
      .attr('d', d => line(d.knowledge))
      .attr('fill', 'none')
      .attr('stroke', d => color[d.cluster])
      .attr('stroke-width', 1.5)
      .attr('opacity', 0.8)
      .on('click', (e, d) => {
        console.log('d:', d.stu_id)
        this.handleLineClick(d)
        this.updateLines()
      })
      .on('mouseover', function(e, d) {
        // console.log('d:over!!!', d)
        tooltip.style('visibility', 'visible')
          .html(`student: ${d.stu_id} <br>cluster: ${d.cluster}`)
          .style('left', (e.pageX + 10) + 'px')
          .style('top', (e.pageY + 10) + 'px')
      })
      .on('mouseout', function() {
        tooltip.style('visibility', 'hidden')
      })
      // 绘制坐标轴
      g.selectAll('.axis')
      .data(dimensions)
      .enter()
      .append('g')
      .attr('class', 'axis')
      .attr('transform', d => `translate(${dimensionsX(d)}, ${margin.top})`)
      .each(function() {
        d3.select(this).call(yAxis)
        // console.log(d)
      })
      // 添加标签
      .append('text')
        .attr('y', -9)
        .style('text-anchor', 'middle')
        .text(d => d)
        .style('fill', 'black')
    },
    handleLineClick(d){
      this.toggleSelection(d.stu_id)
    },
    updateLines(){
      // console.log('line', this.lines)
      this.lines
        .style('opacity', 0.7)
      this.lines
        .classed('selected', d => this.getSelection.includes(d.stu_id))
        .style('stroke-width', d => this.getSelection.includes(d.stu_id) ? 5 : 1)
        .style('stroke-linecap', 'round')
        .style('stroke-linejoin', 'round')
        .style('opacity', d => this.getSelection.includes(d.stu_id)? 1 : 0.7)
      }
  },
  watch: {
    //监视被选中的学生实例
    getSelection:{
      handler(){
        // console.log('change!!')
        // this.updateLines()
      },
      deep: true
    },
    async getHadFilter(){
      console.log('had filter change!!PPPP')
      this.$d3.select('#visualizationP').selectAll('*').remove()
      await this.fetchClusterData()      
      this.renderParallel()
    }
  }
};
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
  #visualization {
    border: 1px solid #ccc;
    margin: 20px;
    padding: 0 20px 20px 0;
    box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
    .axis{
      pointer-events: none;
    }
    path{
      z-index:5;
      .selected{
        stroke: #000;
        stroke-width: 5px;
      }
      .selected::before{
        content: '';
        position: absolute;
        width: 100%;
        height: 100%;
        background-color: transparent;
        border: 1px solid #000;
        box-sizing: border-box;
        pointer-events: none;
      }
    }
  }
}

</style>

<template>
  <div class="icon-container">
    <div class="icon-radar"></div>
  </div>
  
</template>
  
<script>
import * as d3 from 'd3';
export default {
  name: 'IconBlock',
  components: {
   
  },
  data() {
    return {
    }
  },
  mounted(){
    this.renderIcon()
    // console.log('o', d3.select('.icon-container'))
  },
  methods: {
    renderIcon(){
      // const d3 = this.$d3
      const height = 50
      const width = 50
      const labelRadius = 18
      const labelCenter = { 
        X: width / 2,
        Y: height / 2
       }
      const svg = d3.select('.icon-radar')
        .html('') // Clear previous content
        .append('svg')
        .attr('width', width - 5)
        .attr('height', height - 5)
      const labelG = svg.append('g')
        .attr('class', 'label-bar')
        .attr('transform', `translate(${labelCenter.X}, ${labelCenter.Y})`)
      
      // 绘制circular bar
      const dimension = [1, 2, 3, 4, 5, 6, 7, 8]
      const num = dimension.length
      const iconData = dimension.map((_, i) => ({ r1: labelRadius * 0.8, r2: labelRadius, index: i }));
      
      const labelArc = d3.arc()
        .innerRadius(d => d.r1)
        .outerRadius(d => d.r2)
        .startAngle(d => d.index * 2 * Math.PI / num)
        .endAngle(d => (1 + d.index) * 2 * Math.PI / num)
        .padAngle(0.08)
        .padRadius(labelRadius * 0.8)
      
      labelG.selectAll('.label-bar')
        .data(iconData)
        .join('g')
        .append('path')
        .attr('fill', '#E6E6E6')
        .attr('d', labelArc)
      
      // 绘制雷达图
      const innerRadius = labelRadius * 0.7
      const iconRadarData = [
        { features: 1, value: 0.7 },
        { features: 2, value: 0.5 },
        { features: 3, value: 0.7 },
        { features: 4, value: 0 },
        { features: 5, value: 0.7 },
        { features: 6, value: 0.5 },
        { features: 7, value: 0.7 },
        { features: 8, value: 1 },
      ]
      console.log(iconRadarData)
      const angleRadar = d3.scaleBand()
          .domain(dimension)
          .range([0, 2 * Math.PI])
          .align(0)
        const radiusR = d3.scaleLinear()
          .domain([0, 1])
          .range([0, innerRadius])
        const radarLine = d3.lineRadial()
          .radius(d => radiusR(d.value))
          .angle(d => angleRadar(d.features))
        
        
        const closedData = [...iconRadarData, iconRadarData[0]]
        labelG.append('path')
          .datum(closedData)
          .attr('fill-opacity', 0.5)
          .attr('stroke', `#E6E6E6`)
          .attr('stroke-width', 1.5)
          .attr('d', radarLine)
          
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
.icon-container{
  height: 50px;
  width: 50px;
}
</style>
  
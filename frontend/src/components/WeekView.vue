<template>
  <div id="week-view">
    <div class="title">
      <span>Week View</span>
      <input class="limit-input" type="number" v-model="limitLength" @change="updateLimit" />
      <div class="limit">limit:</div>
    </div>
    <Simplebar style="height: 550px; width: 98%">
      <div id="visualizationW"></div>
    </Simplebar>
  </div>
</template>

<script>
import { getWeeks } from '@/api/WeekView'
import { mapGetters } from 'vuex'
import Simplebar from 'simplebar-vue'
import 'simplebar-vue/dist/simplebar.min.css'
export default {
  name: 'WeekView',
  data() {
    return {
      WeekData: [],
      // colors:['#ff7f00', '#377eb8', '#4daf4a'],
      limitLength: 4,
      factLength: null
    };
  },
  components: {
    Simplebar
  },
  computed: {
    ...mapGetters(['getHadFilter','getColors']),
    JustClusterData(){
      return this.$store.state.justClusterData
    },
  },
  async created(){
    // this.getWeekData()
  },
  async mounted() {
  },
  update(){
    
  },
  methods: {
    async getWeekData() {
      // 获取题目数据
      const { data } = await getWeeks()
      this.WeekData = data
      console.log('WeekData', this.WeekData)
      this.renderWeekData()
    },
    renderWeekData(){
      // console.log('renderWeekData')
      const d3 = this.$d3
      const data = this.WeekData
      const height = 600
      const width = 790
      const margin = {top: 20, bottom: 20, left: 20, right: 20} 
      const stu_icon = 40
    
      //定义维度
      const numWeeks = d3.max(data.students, d => d.weeks.length)
      const numStudents = data.students.length
      const stu_ids = Object.values(data.students).map(d => d.id.slice(-5))
      // const numKnowledgePoints = 8
      // console.log('numWeek', numWeeks)
      // console.log('numStudents', numStudents)
      // console.log('stu_id', stu_ids)
      
      const svg = d3.select('#visualizationW')
        .append('svg')
        .attr('width',width / 10 * numWeeks)
        .attr('height', (height / 5) * numStudents)
      const g = svg.append('g')
        .attr('transform', `translate(${margin.left + stu_icon}, ${margin.top})`)
      // console.log('g:',g)

      
      // 定义缩放尺
      const weekX = d3.scaleLinear()
      .domain([0, numWeeks + 1])
      .range([0, width / 10 * (numWeeks - 1)])
      // .padding(0.1)

      const studentsY = d3.scaleBand()
      .domain(stu_ids)
      .range([0, (height / 5) * numStudents])
      // .padding(0.1)
      // console.log('studentY', studentsY)

      // 定义坐标轴
      const xAxis = d3.axisTop(weekX)
      const yAxis = d3.axisLeft(studentsY)

      // 绘制坐标轴
      g.append('g').call(xAxis)
      g.append('g').call(yAxis)
      
      // 区分x轴,奇数填充为深色列
      const deepData = []
      for(let i = 1; i <= numWeeks + 1; ){
        i = i + 2
        deepData.push(i)
      }
      g.selectAll('.deepArea')
      .data(deepData)
      .enter()
      .append('g')
      .append('rect')
        .attr('x', d => weekX(d) - width / 20 )
        .attr('y', 2)
        .attr('fill', '#F5F5F5')
        .attr('width', width / 12)
        .attr('height', (height / 5) * numStudents)


      // ------------------每个元素：Bar Radar部分-----------------
      const radius = width / 24
      const innerRadius = 0.4 * radius
      const outerRadius = radius
      const knowledge = Object.keys(data.students[0].weeks[0].scores)
      // console.log('knowledge', knowledge)
      // 定义角度缩放尺
      const angleX = d3.scaleBand()
        .domain(knowledge)
        .range([0, 2 * Math.PI])
        .align(0)
      // 定义半径缩放尺
      const radiusY = d3.scaleLinear()
      .domain([0, 1])
      .range([innerRadius, outerRadius])
      // 定义曲线生成器
      const arc = d3.arc()
          .innerRadius(innerRadius)
          .outerRadius(d => radiusY(d.value))
          .startAngle(d => angleX(d.knowledge))
          .endAngle(d => angleX(d.knowledge) + angleX.bandwidth())
          .padAngle(0.01)
          .padRadius(innerRadius)
      
      const radarData = Object.values(data)[0]
      // console.log('Ovdata:', radarData)
      const transform =  function(scores){
          return Object.entries(scores).map((d) => {
            return {
              'knowledge': d[0], 
              'value': d[1], 
            }
          })
        }

      // 控制
      this.factLength = radarData.length
      // console.log(radarData)
      // 对每个学生
      radarData.forEach((s, i) => {
        if(i >= this.limitLength) return
        // console.log('s:', s)
        const student_id = s.id
        const student_weeks = s.weeks
        const kind  = this.JustClusterData[student_id]
        const student_color = this.getColors[kind]
        // 对每一周
        student_weeks.forEach(w => {
          const position = `translate(${weekX(w.week) + width / 12}, ${studentsY(student_id.slice(-5)) + studentsY.bandwidth() / 2})`
          const radarChartG = g.append('g')
            .attr('class','radar')
            .attr("transform", position)
          //绘制柱状图
          radarChartG.selectAll('.radar')
          .data(transform(w.scores))
          .enter()
          .append('g')
          .append("path")
            .attr('fill', `${student_color}`)
            .attr('d', arc)

          // console.log('w:', transform(w.scores))
          // console.log('w.week',w.week)
          // console.log('student_id', student_id)
      

          // 绘制标签圆
          const labelOuterRadius = innerRadius
          const labelInnerRadius = 0.7 * labelOuterRadius
          const innerCircleRadius = 0.8* labelInnerRadius
          const labelArc = d3.arc()
              .innerRadius(d => d.r1)
              .outerRadius(d => d.r2)
              .startAngle(0)
              .endAngle(Math.PI * 2)

          const circleOuterData = [{
            r1: labelInnerRadius,
            r2: labelOuterRadius
          }]
          const circleMiddleData = [{
            r1:innerCircleRadius,
            r2: labelInnerRadius
          }]
          const circleInnerData = [{
            r1: 0,
            r2: innerCircleRadius
          }]
          const labelOG = g.append('g')
            .attr('class','label-circle')
            .attr("transform", position)
          // console.log('labelG', labelG)
          const labelMG = g.append('g')
            .attr('class','label-circle')
            .attr("transform", position)
          const labelG = g.append('g')
            .attr('class','label-circle')
            .attr("transform", position)

          labelOG.selectAll('.label-circle')
          .data(circleOuterData)
          .enter()
          .append('g')
          .append("path")
            .attr('fill', `${'#FFFFFF'}`)
            .attr('d', labelArc)

          labelMG.selectAll('.label-circle')
          .data(circleMiddleData)
          .enter()
          .append('g')
          .append("path")
            .attr('fill', `${'#eee'}`)
            .attr('d', labelArc)
            
          labelG.selectAll('.label-circle')
          .data(circleInnerData)
          .enter()
          .append('g')
          .append("path")
            .attr('fill', `${'#FFFFFF'}`)
            .attr('d', labelArc)


        })//forEach.w

      }) // forEach.s
      
    },
    updateLimit(){
      if(this.limitLength > this.factLength) {
        this.limitLength = this.factLength
        return
      } 
      if(this.limitLength < 1) {
        this.limitLength = 1
        return
      }
      // console.log('updateLimit', this.limitLength)
      // 清除之前的SVG元素
      const d3 = this.$d3
      d3.select('#visualizationW').selectAll('*').remove();
      // 重新渲染图表
      this.renderWeekData()
    }
  },
  watch: {
    getHadFilter(){
      this.$d3.select('#visualizationW').selectAll('*').remove()
      this.getWeekData()
    }
  }
};
</script>

<style scoped lang="less">
#week-view {
  width: 100%;
  height: 620px;
  border-radius: 5px;
  padding-top: 2px;
  background-color: #fff;
  .title{
    height: 20px;
    margin: 10px 0;
    padding-bottom: 7px;
    border-bottom: 1px solid #ccc;
    span{
      height: 20px;
      width: inherit;
      font-size: 20px;
      font-weight: bold;
      padding-left: 10px;
      margin: 10px 5px;
    }
    .limit{
      float: right;
      font-weight: bold;
      padding-right: 10px;
    }
    .limit-input{
      float: right;
      width: 30px;
      height: 18px;
      text-align: center;
      line-height: 15px;
      margin-right: 10px;
      padding-left: 17px;
      border: 0;
      font-weight: bold;
      border-bottom: 1px solid #000;
    }
  }
}
</style>

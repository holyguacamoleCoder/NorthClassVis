<template>
  <div id="week-view">
    <div class="title">
      <span>Week View</span>
      <select class="kind-select" v-model="selectedKind" @change="updateKind">
        <option value="">All Kinds</option>
        <option v-for="i in 3" :key="i" :value="i">{{ i - 1 }}</option>
      </select>
      <div class="limit">kind:</div>
    </div>
    <Simplebar style="height: 560px; width: 98%">
      <LoadingSpinner v-if=loading />
      <div id="visualizationW">
      </div>
    </Simplebar>
  </div>
</template>

<script>
import { getWeeks } from '@/api/WeekView'
import { mapState, mapGetters } from 'vuex'
import Simplebar from 'simplebar-vue'
import 'simplebar-vue/dist/simplebar.min.css'
import LoadingSpinner from './LoadingSpinner.vue'

export default {
  name: 'WeekView',
  components: {
    Simplebar,
    LoadingSpinner
  },
  data() {
    return {
      loading: true,
      WeekData: [],
      selectedKind: '',
    }
  },
  computed: {
    ...mapState(['configLoaded']),

    ...mapGetters(['getHadFilter', 'getColors']),
    JustClusterData() {
      return this.$store.state.justClusterData
    },
    filteredData() {
      if (!this.selectedKind) return this.WeekData.students
      return this.WeekData.students.filter(s => this.JustClusterData[s.id] === this.selectedKind - 1)
    }
  },
  async created() {
    // await this.getWeekData()
  },
  methods: {
    async getWeekData() {
      const { data } = await getWeeks()
      this.WeekData = data
      // console.log('WeekData', this.WeekData)
      this.renderWeekData()
    },
    renderWeekData() {
      const d3 = this.$d3
      const height = 600
      const width = 1000
      const margin = { top: 20, bottom: 20, left: 20 ,right: 20 }
      const stu_icon = 40
      const weekLabelHeight = 20 // 周标签高度
      const filteredData = this.filteredData

      // 定义维度
      const numWeeks = d3.max(filteredData, d => d.weeks.length)

      // 根据选中的 kind 过滤数据
      const numStudents = filteredData.length

      const svg = d3.select('#visualizationW')
        .append('svg')
        .attr('width', margin.left + margin.right + stu_icon + width / 9 * (numWeeks + 1))
        .attr('height', (height / 5) * numStudents + weekLabelHeight)
      const g = svg.append('g')

      // 定义rect组，放置深色矩形和各个环
      const rg = g.append('g')
        .attr('transform', `translate(${margin.left + stu_icon}, ${weekLabelHeight})`)

      // 定义缩放尺
      const weekX = d3.scaleLinear()
        .domain([0, numWeeks])
        .range([0, width / 9 * (numWeeks)])

      const studentsY = d3.scaleBand()
        .domain(d3.range(numStudents))
        .range([0, (height / 5) * numStudents])

      // 计算每个周的宽度
      const weekWidth = weekX(1) - weekX(0)

      // 区分x轴,奇数填充为深色列
      for (let i = 1; i <= numWeeks + 1; i++) {
        if (i % 2 !== 0) {
          rg.append('rect')
            .attr('x', weekX(i) - weekWidth / 2)
            .attr('y', -weekLabelHeight)
            .attr('fill', '#F5F5F5') // 奇数列为浅灰色
            .attr('width', weekWidth)
            .attr('height', (height / 5) * numStudents + weekLabelHeight)
        }

        // 绘制每个周的标签
        rg.append('text')
          .attr('x', weekX(i))
          .attr('y', 0)
          .text(`Week${i}`)
          .attr('text-anchor', 'middle')
          .attr('font-size', 14)
          .attr('font-weight', 'bold')
      }

      // ------------------每个元素：Bar Radar部分-----------------
      const radius = width / 24
      const innerRadius = 0.4 * radius
      const outerRadius = radius
      const knowledge = Object.keys(filteredData[0].weeks[0].scores)

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
        .padAngle(0.05)
        .padRadius(innerRadius)

      filteredData.forEach((s, i) => {
        const student_id = s.id
        const student_weeks = s.weeks
        const kind = this.JustClusterData[student_id]
        const student_color = this.getColors[kind]

        // 定义legend组
        const lg = g.append('g')
          .attr('transform', `translate(${margin.left + stu_icon}, ${weekLabelHeight})`)

        // 渲染学生名称
        const labelPadding = 5 // 背景矩形的内边距
        const textElement = lg.append('text')
          .attr('x', (margin.left - stu_icon) / 2)
          .attr('y', studentsY(i) + studentsY.bandwidth() / 2 + stu_icon)
          .attr('dy', '.35em')
          .attr('text-anchor', 'middle')
          .style('font-size', '14px')
          .text(student_id.slice(-5))

        let Bbox = textElement.node().getBBox()

        // 添加背景矩形
        lg.insert('rect', ':first-child') // 在第一个子元素之前插入，确保它位于文本下方
          .attr('x', Bbox.x - labelPadding) // 留出一些额外的空间
          .attr('y', Bbox.y - labelPadding)
          .attr('rx', (Bbox.height + labelPadding * 2) / 2) // 圆角半径
          .attr('ry', (Bbox.height + labelPadding * 2) / 2)
          .attr('width', Bbox.width + labelPadding * 2) // 考虑额外空间
          .attr('height', Bbox.height + labelPadding * 2)
          .attr('fill', '#f0f0f0') // 背景颜色

        // 渲染学生头像
        const userAvatar = '/images/user_avatar.png'
        lg.append('image')
          .attr('x', margin.left / 2 - stu_icon)
          .attr('y', studentsY(i) + studentsY.bandwidth() / 2 - stu_icon / 2)
          .attr('width', stu_icon)
          .attr('height', stu_icon)
          .attr('href', userAvatar)

        // 对每一周
        student_weeks.forEach(w => {
          const position = `translate(${weekX(w.week) + weekWidth}, ${studentsY(i) + studentsY.bandwidth() / 2})`
          const radarChartG = rg.append('g')
            .attr('class', 'radar')
            .attr("transform", position)

          // 绘制柱状图
          radarChartG.selectAll('.radar')
            .data(this.transformScores(w.scores))
            .enter()
            .append('g')
            .append("path")
            .attr('fill', `${student_color}`)
            .attr('d', arc)

          // 绘制标签圆
          const labelOuterRadius = innerRadius
          const labelInnerRadius = 0.7 * labelOuterRadius
          const innerCircleRadius = 0.8 * labelInnerRadius
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
            r1: innerCircleRadius,
            r2: labelInnerRadius
          }]
          const circleInnerData = [{
            r1: 0,
            r2: innerCircleRadius
          }]

          const labelOG = rg.append('g')
            .attr('class', 'label-circle')
            .attr("transform", position)

          const labelMG = rg.append('g')
            .attr('class', 'label-circle')
            .attr("transform", position)

          const labelG = rg.append('g')
            .attr('class', 'label-circle')
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
        }) // forEach.w
      }) // forEach.s
    },
    transformScores(scores) {
      return Object.entries(scores).map(([knowledge, value]) => ({ knowledge, value }))
    },
    updateKind() {
      // 清除之前的SVG元素
      const d3 = this.$d3
      d3.select('#visualizationW').selectAll('*').remove()
      // 重新渲染图表
      this.renderWeekData()
    }
  },
  watch: {
    getHadFilter() {
      this.$d3.select('#visualizationW').selectAll('*').remove()
      this.getWeekData()
    }
  }
}
</script>

<style scoped lang="less">
#week-view {
  .title {
    border-bottom: 1px solid #ccc; 
    width: 100%;
    padding-top: 10px;
    padding-bottom: 5px;
    margin-bottom: 5px;
    span {
      height: 20px;
      width: inherit;
      font-size: 20px;
      font-weight: bold;
      padding-left: 10px;
      margin: 10px 5px;
    }

    .kind-select {
      float: right;
      width: 100px;
      height: 20px;
      margin-right: 10px;
      padding-left: 5px;
      border: 1px solid #ccc;
      font-size: 14px;
    }

    .limit {
      float: right;
      font-weight: bold;
      padding-right: 10px;
    }
  }
  .simplebar-content-wrapper {
    /*添加阴影*/
    box-shadow: 10px 10px 10px rgba(0, 0, 0, 0.1);
    border-radius: 5px;
  }
}
</style>





<template>
  <div id="week-view">
    <div class="title">
      <span>Week View</span>
      <div class="view-mode-switch">
        <span class="mode-label">Mode: {{showPeakView ? 'p' : 'r'}}</span>
        <label class="switch">
          <input type="checkbox" class="switch-input" v-model="showPeakView" />
          <span class="slider round"></span>
        </label>
      </div>
      <select class="kind-select" v-model="selectedKind" @change="updateKind">
        <option value="">All Kinds</option>
        <option v-for="i in 3" :key="i" :value="i">{{ i - 1 }}</option>
      </select>
      <select 
        v-model="selectedDay" 
        @change="loadData"
        :disabled="!showPeakView"
        class="day-select"
        title="Only available in Peak View mode"
      >
        <option v-for="day in 7" :key="day" :value="day">Day {{ day }}</option>
      </select>
      <div class="limit">kind:</div>
    </div>
    <Simplebar style="height: 550px; width: 98%">
      <LoadingSpinner v-if=loading />
      <div class="wait-prompt"  v-if="isWaiting">Waiting for brush :) ...</div>
      <div id="visualizationW"></div>
    </Simplebar>
  </div>
</template>

<script>
import { getWeeks, getPeaks } from '@/api/WeekView'
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
      debugger: true,
      loading: false,
      isWaiting: true,
      WeekData: [],
      PeakData:[],
      selectedKind: '',
      showPeakView: false,
      selectedDay: 5
    }
  },
  computed: {
    ...mapState(['configLoaded']),
    ...mapGetters(['getStudentClusterInfo','getSelectedIds', 'getSelectedData','getColors']),
    filteredWeekData() {
      if (!this.selectedKind) return this.WeekData.students
      return this.WeekData.students.filter(s => this.getStudentClusterInfo[s.id] === this.selectedKind - 1)
    },
    filteredPeakData() {
      if (!this.selectedKind) return this.PeakData.peaks
      return this.PeakData.peaks.filter(s => this.getStudentClusterInfo[s.id] === this.selectedKind - 1)
    }
  },
  async created() {
  },
  methods: {
    async getWeekData(stu_ids) {
      const { data } = await getWeeks(stu_ids)
      this.WeekData = data
      // console.log('WeekData', this.WeekData)
      this.renderWeekData()
    },
    async getPeakData(stu_ids, day) {
      const { data } = await getPeaks(stu_ids, day)
      this.PeakData = data
      this.renderPeakData()
    },
    renderWeekData() {
      const d3 = this.$d3
      const height = 600
      const width = 1000
      const margin = { top: 20, bottom: 20, left: 20 ,right: 20 }
      const stu_icon = 40
      const weekLabelHeight = 20 // 周标签高度
      const filteredWeekData = this.filteredWeekData

      // 定义维度
      const numWeeks = d3.max(filteredWeekData, d => d.weeks.length)

      // 根据选中的 kind 过滤数据
      const numStudents = filteredWeekData.length

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
      const knowledge = Object.keys(filteredWeekData[0].weeks[0].scores)

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
      const colors = this.getColors
      const studentClusterInfo = this.getStudentClusterInfo
       filteredWeekData.forEach((s, i) => {
        const student_id = s.id
        const student_weeks = s.weeks
        const kind = studentClusterInfo[student_id]
        // console.log(kind)
        const student_color = colors[kind]

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
          // const circleMiddleData = [{
          //   r1: innerCircleRadius,
          //   r2: labelInnerRadius
          // }]
          const circleInnerData = [{
            r1: 0,
            r2: innerCircleRadius
          }]
          // outer外圈圆
          const labelOG = rg.append('g')
            .attr('class', 'label-circle')
            .attr("transform", position)
          // middle灰色圈
          // const labelMG = rg.append('g')
          //   .attr('class', 'label-circle')
          //   .attr("transform", position)
          // 外围白色圈
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

          // labelMG.selectAll('.label-circle')
          //   .data(circleMiddleData)
          //   .enter()
          //   .append('g')
          //   .append("path")
          //   .attr('fill', `${'#eee'}`)
          //   .attr('d', labelArc)

          labelG.selectAll('.label-circle')
            .data(circleInnerData)
            .enter()
            .append('g')
            .append("path")
            .attr('fill', `${student_color}`)
            .attr('opacity', 0.5)
            .attr('d', labelArc)
        }) // forEach.w
      }) // forEach.s
    },
    renderPeakData() {
      const d3 = this.$d3;
      const height = 600;
      const width = 1000;
      const margin = { top: 20, bottom: 20, left: 20, right: 20 };
      const stu_icon = 40;
      const weekLabelHeight = 20; // 周标签高度
      const filteredPeakData = this.filteredPeakData;
    
      // 定义维度
      const numWeeks = d3.max(filteredPeakData, d =>
        d3.max(d.weeks, w => w.week)
      );
    
      // 根据选中的 kind 过滤数据
      const numStudents = filteredPeakData.length;
    
      const svg = d3.select('#visualizationW')
        .append('svg')
        .attr('width', margin.left + margin.right + stu_icon + width / 9 * (numWeeks + 1))
        .attr('height', (height / 5) * numStudents + weekLabelHeight);
      const g = svg.append('g');
    
      const rg = g.append('g')
        .attr('transform', `translate(${margin.left + stu_icon}, ${weekLabelHeight})`);
    
      const weekX = d3.scaleLinear()
        .domain([0, numWeeks])
        .range([0, width / 9 * (numWeeks)]);
    
      const studentsY = d3.scaleBand()
        .domain(d3.range(numStudents))
        .range([0, (height / 5) * numStudents]);
    
      const weekWidth = weekX(1) - weekX(0);
    
      // 添加 tooltip
      const tooltip = d3.select("body").append("div")
        .attr("class", "tooltip")
        .style("position", "absolute")
        .style("text-align", "center")
        .style("padding", "4px")
        .style("background", "#fff")
        .style("border", "0px")
        .style("border-radius", "8px")
        .style("pointer-events", "none")
        .style("font-size", "12px")
        .style("opacity", 0);
    
      // 区分x轴奇数列
      for (let i = 1; i <= numWeeks + 1; i++) {
        if (i % 2 !== 0) {
          rg.append('rect')
            .attr('x', weekX(i) - weekWidth / 2)
            .attr('y', -weekLabelHeight)
            .attr('fill', '#F5F5F5')
            .attr('width', weekWidth)
            .attr('height', (height / 5) * numStudents + weekLabelHeight);
        }
      
        rg.append('text')
          .attr('x', weekX(i))
          .attr('y', 0)
          .text(`Week${i}`)
          .attr('text-anchor', 'middle')
          .attr('font-size', 14)
          .attr('font-weight', 'bold');
      }
    
      const colors = this.getColors;
      const studentClusterInfo = this.getStudentClusterInfo;
    
      filteredPeakData.forEach((s, i) => {
        const student_id = s.id;
        const student_weeks = s.weeks;
        const kind = studentClusterInfo[student_id];
        const student_color = colors[kind];
      
        const lg = g.append('g')
          .attr('transform', `translate(${margin.left + stu_icon}, ${weekLabelHeight})`);
      
        const labelPadding = 5;
        const textElement = lg.append('text')
          .attr('x', (margin.left - stu_icon) / 2)
          .attr('y', studentsY(i) + studentsY.bandwidth() / 2 + stu_icon)
          .attr('dy', '.35em')
          .attr('text-anchor', 'middle')
          .style('font-size', '14px')
          .text(student_id.slice(-5));
      
        let Bbox = textElement.node().getBBox();
      
        lg.insert('rect', ':first-child')
          .attr('x', Bbox.x - labelPadding)
          .attr('y', Bbox.y - labelPadding)
          .attr('rx', (Bbox.height + labelPadding * 2) / 2)
          .attr('ry', (Bbox.height + labelPadding * 2) / 2)
          .attr('width', Bbox.width + labelPadding * 2)
          .attr('height', Bbox.height + labelPadding * 2)
          .attr('fill', '#f0f0f0');
      
        const userAvatar = '/images/user_avatar.png';
        lg.append('image')
          .attr('x', margin.left / 2 - stu_icon)
          .attr('y', studentsY(i) + studentsY.bandwidth() / 2 - stu_icon / 2)
          .attr('width', stu_icon)
          .attr('height', stu_icon)
          .attr('href', userAvatar);
      
        const peaKHeight = 25;
        const peakWidth = weekWidth / 2;
      
        const positionYBase = studentsY(i) + 4 * studentsY.bandwidth() / 5;
      
        const yScale = d3.scaleLinear()
          .domain([0, 30])
          .range([positionYBase, positionYBase - peaKHeight]);
      
        student_weeks.forEach(w => {
          const positionX = weekX(w.week) + weekWidth - weekWidth / 4;
          const positionY = positionYBase;
        
          const firstHalfHeight = yScale(w.Mon_to_Day);
          const secondHalfHeight = yScale(w.after_Day_to_Sun);
        
          const defs = svg.append("defs");
        
          const grad1 = defs.append("linearGradient")
            .attr("id", `grad1-${s.id}-week${w.week}`)
            .attr("x1", "0%")
            .attr("y1", "0%")
            .attr("x2", "0%")
            .attr("y2", "100%");
          grad1.append("stop")
            .attr("offset", "0%")
            .attr("style", `stop-color:${student_color};stop-opacity:1`);
          grad1.append("stop")
            .attr("offset", "100%")
            .attr("style", "stop-color:#fff;stop-opacity:1");
      // 前半周三角形
      // const frontTriangle = 
      rg.append("polygon")
        .attr("points", `${positionX},${positionY} ${positionX + peakWidth / 2},${firstHalfHeight} ${positionX + peakWidth},${positionY}`)
        .attr("fill", `url(#grad1-${s.id}-week${w.week})`)
        .attr("opacity", 0.8)
        .on("mouseover", (event) => {
          tooltip.transition().duration(200).style("opacity", 0.9);
          tooltip.html(`
            Student: <strong>${s.id}</strong><br/>
            Week: <strong>${w.week}</strong><br/>
            First Half: <strong>${w.Mon_to_Day}</strong>
          `)
          .style("left", `${event.pageX}px`)
          .style("top", `${event.pageY - 28}px`);
        })
        .on("mousemove", (event) => {
          tooltip.style("left", `${event.pageX}px`).style("top", `${event.pageY - 28}px`);
        })
        .on("mouseout", () => {
          tooltip.transition().duration(500).style("opacity", 0);
        });
    
      // 后半周三角形
      // const backTriangle = 
      rg.append("polygon")
        .attr("points", `${positionX + peakWidth / 4},${positionY} ${positionX + peakWidth / 2},${secondHalfHeight} ${positionX + 3 * peakWidth / 4},${positionY}`)
        .attr("fill", `${student_color}`)
        .attr("opacity", 0.7)
        .on("mouseover", (event) => {
          tooltip.transition().duration(200).style("opacity", 0.9);
          tooltip.html(`
            Student: <strong>${s.id}</strong><br/>
            Week: <strong>${w.week}</strong><br/>
            Second Half: <strong>${w.after_Day_to_Sun}</strong>
          `)
          .style("left", `${event.pageX}px`)
          .style("top", `${event.pageY - 28}px`);
        })
        .on("mousemove", (event) => {
          tooltip.style("left", `${event.pageX}px`).style("top", `${event.pageY - 28}px`);
        })
        .on("mouseout", () => {
          tooltip.transition().duration(500).style("opacity", 0);
        });
      
          // 连接线
          rg.append("line")
            .attr("x1", positionX + peakWidth / 2)
            .attr("y1", firstHalfHeight)
            .attr("x2", positionX + peakWidth / 2)
            .attr("y2", secondHalfHeight)
            .attr("stroke-width", 1)
            .attr("stroke", "#fff");
        }); // w
      }); // s
    },
    transformScores(scores) {
      return Object.entries(scores).map(([knowledge, value]) => ({ knowledge, value }))
    },
    updateKind() {
      // 清除之前的SVG元素
      const d3 = this.$d3
      d3.select('#visualizationW').selectAll('*').remove()
      if (this.showPeakView) {
      this.renderPeakData();
      } else {
        this.renderWeekData();
      }
    },
    async loadData(render = true) {
      this.loading = true
      this.$d3.select('#visualizationW').selectAll('*').remove()
      this.WeekData = []
      this.PeakData = []
      if (render) {
        if (this.showPeakView) {
          await this.getPeakData(this.getSelectedIds, this.selectedDay);
        } else {
          await this.getWeekData(this.getSelectedIds);
        }
      }
      this.loading = false
    }
  },
  watch: {
    configLoaded(newVal) {
      if (newVal && this.debugger) {
        // 重新加载逻辑
        this.loadData(false)
        this.isWaiting = true
      }
    },
    async getSelectedData(newVal) {
      if (!newVal) {
        return
      }
      this.isWaiting = false
      this.loadData() 
    },
    // 监听 switch 变化，重新加载数据并渲染
    showPeakView() {
      this.isWaiting = false
      this.loadData()
    },
    selectedDay() {
      if(this.showPeakView){
        this.isWaiting = false;
        this.loadData();
      }
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
    position: relative;

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

    /* 新增：视图切换开关 */
    .view-mode-switch {
      float: right;
      display: flex;
      align-items: center;
      margin-right: 10px;
      height: 20px;
      line-height: 20px;
      font-size: 14px;
      color: #333;

      .mode-label {
      margin-right: 10px;

        font-size: 14px;
        color: #333;
      }
    }

    /* 开关样式 */
    .switch {
      position: relative;
      display: inline-block;
      width: 40px;
      height: 20px;
    }

    .switch input {
      opacity: 0;
      width: 0;
      height: 0;
      
    }

    .slider {
      position: absolute;
      cursor: pointer;
      top: 0;
      left: 0;
      right: 0;
      bottom: 0;
      background-color: steelblue;
      transition: 0.4s;
      border-radius: 34px;
      margin: 0;

      &:before {
        position: absolute;
        content: "";
        font-size: 18px;
        text-align: center;
        line-height: 14px;
        height: 14px;
        width: 14px;
        left: 3px;
        bottom: 3px;
        background-color: white;
        transition: 0.4s;
        border-radius: 50%;
      }
    }

    .switch input:checked + .slider {
      background-color: #4caf50;
    }

    .switch input:checked + .slider:before {
      transform: translateX(18px);
    }

    .slider.round {
      border-radius: 34px;
      width: 25px;

      &:before {
        border-radius: 50%;
      }
    }
  }

  .wait-prompt {
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translateX(-50%) translateY(-50%);
    font-size: 40px;
    font-weight: bold;
    color: #eee;
  }

  .simplebar-content-wrapper {
    box-shadow: 10px 10px 10px rgba(0, 0, 0, 0.1);
    border-radius: 5px;
  }

  .day-select {
    float: right;
    width: 80px;
    height: 20px;
    margin-right: 10px;
    padding-left: 5px;
    border: 1px solid #ccc;
    font-size: 14px;
  
    &:disabled {
      background-color: #e9e9e9;
      color: #999;
      cursor: not-allowed;
      opacity: 0.6;
    }
  }
}
</style>





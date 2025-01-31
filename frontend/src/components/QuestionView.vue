<template>
  <div id="question-view" style="padding: 10px;">
    <div class="title">
      <span>Question View</span>
      <Dropdown>
        <!-- trigger element -->
        <template #trigger>
          <button type="button" style="font-weight: bold">
            {{displayButton}}
          </button>
        </template>
        <!-- contents display in dropdown -->
          <form id="checkboxs" name="myForm">
           <div class="selectK" v-for="(item,index) in CheckoutData" :key="index"  style="border-radius: 5px; padding: 5px">
             <input 
             type="checkbox"
             checked
             :name="item.label"
             v-model="item.checked"
             @change="handleCheck">
             <label
             style="list-style: none;
             width: 80px;
             border-bottom: 1px solid #ccc;
             margin-top: 5px;
             padding-bottom: 8px;
             text-align: center;"
             >{{ item.label }}</label>
            </div>
            
            <div class="all" style="border-radius: 5px; padding: 5px">
              <input 
              name="all"
              type="checkbox"
              class="knowledge-list"
              checked
              v-model="CheckoutAllData"
              @change="handleAllCheck"
              >
              <label 
              for="all"
              style="list-style: none;
              width: 80px;
              border-bottom: 1px solid #ccc;
              margin-top: 5px;
              padding-bottom: 8px;
              text-align: center;"
              >All</label>
            </div>
          </form>
          
          
      </Dropdown>
      <div class="filter">Knowledge:</div>
    </div>
    
    <Simplebar style="height: 550px">
      <div id="visualizationQ"></div>
    </Simplebar>
  </div>
</template>

<script>
import { getQuestions } from '@/api/QuestionView'
import { mapGetters } from 'vuex'
import Simplebar from 'simplebar-vue'
import 'simplebar-vue/dist/simplebar.min.css'
import Dropdown from 'v-dropdown'
export default {
  name: 'QuestionView',
  components:{
    Simplebar,
    Dropdown
  },
  data() {
    return {
      QuestionData: [],
      KnowledgeArray: null,
      CheckoutData: [],
      CheckoutAllData: true
    };
  },
  async mounted() {
    this.getQuestionData()
  },
  computed:{
    ...mapGetters(['getHadFilter']),
    displayButton(){
      if(this.CheckoutAllData) return 'All'
      if(this.CheckoutData.some(item => item.checked)) return 'Part'
      else return 'none'
    }
  },
  methods: {
    async getQuestionData() {
      // 获取问题数据
      const { data } = await getQuestions()
      this.QuestionData = data
      console.log('Qdata:', data)

      this.KnowledgeArray = Object.keys(data)
      this.KnowledgeArray.forEach(item => {
        this.CheckoutData.push({label:item, checked: true})              
      })
      // map['all'] = true
      this.renderQuestion()
    },
    // 渲染题目视图数据
    renderQuestion(){
      const d3 = this.$d3
      const width = 650
      const height = 1300
      const margin = { top: 30, right: 20, bottom: 20, left: 20 }
      const innerWidth = width - margin.left - margin.right
      const timelineHeight = 50
      const distributionHeight = 30
      const QtitleHeight = 20
      const data = Object.entries(this.QuestionData).filter((item) => {
        const k = item[0]
        let v = null
        this.CheckoutData.forEach(iitem => {
          if(iitem.label === k) {
            v = iitem.checked
            return
          }
        })
        return v
      })
      console.log('ddd', data)
      // 获取可视化目标容器
      const main = d3.select('#visualizationQ')
      .attr('width', width)
      .attr('height', height)
      // 给容器添加组
      const g = main.append('g')
          .attr('transform', `translate(${margin.left}, ${margin.top})`)
      // 添加知识点容器
      const knowledgePanel = g.selectAll('.knowledge-panel')
                  .data(data)
                  .enter()
                  .append('svg')
                  .attr('class', 'knowledge-panel')
                  .attr('width', width)
                  .attr('height', d => 170 * d[1].length)
                  .attr('y', (d, i) => i * 700)
                  .attr('fill', 'black')
      console.log('knowledgePanel:', knowledgePanel)
      // 给每个知识点绘制组
      const gg = knowledgePanel.append('g')
          .attr('transform', `translate(${margin.left}, ${margin.top})`)
     
      // 绘制知识点标题
      gg.append('text').text(d => 'K - ' + d[0])
      .attr('font-weight', 700)
      .attr('font-size', 20)
      
      // 添加题目容器
      const questionPanel = gg.selectAll('.question-panel')
      .data(d => d[1])
      .enter()
      .append('g')
      .attr('class', 'question-panel')
      // 给每个题目添加组
      const ggg = questionPanel.append('g')
      .attr('transform', (d, i) => `translate(0, ${i * (timelineHeight + distributionHeight +  + QtitleHeight + margin.top * 2) + margin.top})`)
      // console.log('ggg:', ggg)
      
      // 绘制题目标题
      ggg.append('text').text(d => 'Q - ' + d.title_id.slice(-5))
      
      // 绘制时间轴图图表
      ggg.append('svg')
      .attr('class', 'timeline-chart')
      .each(function(d) {
        const svg = d3.select(this)
        .attr('width', innerWidth)
        .attr('height', timelineHeight + margin.top * 2)
        // console.log('d', d)

        // 添加组
        const tg = svg.append('g')
        .attr('transform', `translate(0, 0)`)

        // 定义缩放尺
        const timelineX = d3.scaleTime()
        .domain(d3.extent(d.timeline, dd => new Date(dd.date)))
        .range([0, innerWidth])
        const submissionsY = d3.scaleLinear()
        .domain([0, d3.max(d.timeline, dd => dd.submission_count)])
        .range([timelineHeight, 0])

        // 定义面积生成器
        const area = d3.area()
        .x(dd => timelineX(new Date(dd.date)))
        .y1(submissionsY(0))
        .y0(dd => submissionsY(dd.submission_count))

        // 添加面积图
        tg.append('path')
        .attr('class', 'area')
        .attr('d', area(d.timeline))
        .attr('fill', 'steelblue')
        .attr('stroke', '#000')
        .on('mouseover', function(){
          d3.select(this).attr('opacity', 0.5)
        })
        .on('mouseout', function(){
          d3.select(this).attr('opacity', 1)
        })


        // 定义坐标轴
        const xAxis = d3.axisBottom(timelineX)
        const yAxis = d3.axisLeft(submissionsY)
        // 添加坐标轴
        tg.append('g').call(xAxis)
        .attr('transform', `translate(0, ${timelineHeight})`)
        tg.append('g').call(yAxis)

        // 创建tooltip
        const tooltip = d3.select('body').append('div')
        .attr('class', 'tooltip')
        .style('position', 'absolute')
        .style('visibility', 'hidden') 
        .style('background-color', 'white')
        .style('border', '1px solid black')
        .style('padding', '5px')

        // 添加交互
        tg.selectAll('.dot')
        .data(d.timeline)
        .enter().append('circle')
        .attr('class', 'dot')
        .attr('cx', dd => timelineX(new Date(dd.date)))
        .attr('cy', dd => submissionsY(dd.submission_count))
        .attr('r', 5)
        .attr('opacity', 0.1)
        .attr('fill', '#ccc')
        .on('mouseover', function(event, dd) {
          d3.select(this).attr('r', 10).attr('opacity', 0.5)
          tooltip.style('visibility', 'visible')
          .html(`<p>日期:${dd.date}</p>
                <p>提交次数:${dd.submission_count}</p>
                <p>平均分数:${dd.average_score.toFixed(2)}</p>
                `)
          tooltip.style('top', `${event.pageY - 28}px`)
          .style('left', `${event.pageX + 10}px`)
        })
        .on('mouseout', function() {
          d3.select(this).attr('r', 2).attr('opacity', 0.2)
          tooltip.style('visibility', 'hidden')
        })
      })


      // 添加每一个矩形
      // 绘制分数图像分布
      const distributionCharts = ggg.selectAll('.distribution-chart')
          .data(d => d.distribution)
          .enter()
          .append('svg')
          .attr('class', 'distribution-chart')
          .attr('width', width)
          .attr('height', 200)
      // 为每个分数绘制组
      const scoreG = distributionCharts.append('g')
      .attr('transform', `translate(0, ${margin.top + timelineHeight + QtitleHeight})`)
      // 定义缩放尺
      const xScale = d3.scaleLinear()
      .domain([0, 100])
      .range([0, width])
      // const color = {0: '#3b82f6', 1: '#f97316', 2: '#10b981', 3: '#8b5cf6', 4:'#ef4444'}
      let currentWidth = 0
      // 绘制分数
      scoreG.append('text').text(d => d.percentage != 0 ? d.score : '')
      .attr('x', d => {
        const width = xScale(d.percentage)
        currentWidth += width
        // console.log('currentWidth:', currentWidth)
        return width
      })
      // 绘制分数分布
      currentWidth = 0
      scoreG.append('rect')
      .attr('x', currentWidth)
      .attr('width', d => {
        const width = xScale(d.percentage)
        currentWidth += width
        // console.log('currentWidth:', currentWidth)
        return width
      })
      .attr('height', distributionHeight - 10)
      .attr('fill', d => {
        const score = d.score
        return `rgb(${255 - Math.min(score * 20, 255)}, 0, 0)`
      })
      .attr('opacity', 0.5)
      .attr('rx', 10)
    },
    handleCheck(e){
      console.log(e.target.name)
      this.CheckoutData.checked = !this.CheckoutData.checked
      this.CheckoutAllData = this.CheckoutData.every(item => item.checked)
      const d3 = this.$d3
      d3.select('#visualizationQ').selectAll('*').remove();
      // 重新渲染图表
      this.renderQuestion()
      // console.log('change!!!')
    },
    handleAllCheck(){
      if(this.CheckoutData.every(item => item.checked) || this.CheckoutData.every(item => !item.checked))
        this.CheckoutData.forEach(item => item.checked = !item.checked)
      else{
        this.CheckoutData.forEach(item => item.checked = this.CheckoutAllData)
      }
      const d3 = this.$d3
      d3.select('#visualizationQ').selectAll('*').remove();
      // 重新渲染图表
      this.renderQuestion()
      console.log('change!!!')
    }
  },
  watch: {
    getHadFilter(){
      // console.log('had filter change!!QQQ')
      this.$d3.select('#visualizationQ').selectAll('*').remove()
      this.getQuestionData()
    }
  }
};
</script>

<style scoped lang="less">
#question-view {
  height: 620px;
  background-color: #fff;
  padding: 20px;
  border-radius: 5px;
  box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1);
  .title {
    border-bottom: 1px solid #ccc;
    padding-bottom: 7px;
    span{
      font-size: 17px;
      font-weight:    bold;
      padding-bottom: 10px;
      margin-bottom: 20px;
      padding-left: 10px;
    }
    .filter{
      float: right;
      font-weight:    bold;
      font-size: 17px;
      padding-right: 10px;
    }
    
    .v-dropdown-trigger{
      float: right;
      button{
        border: 0;
        margin-top: 5px;
        margin-right: 5px;
        background-color: #fff;
        padding: 0;
      }
    }
  }
    .question {
    margin-bottom: 20px;
    .progress {
      background-color: #f5f5f5;
      border-radius: 5px;
      overflow: hidden;
      margin-bottom: 10px;
    }
    .progress-bar {
      float: left;
      height: 20px;
      background-color: #3b82f6;
    }
  }
}
.highlight{
  color:#3b82f6;
}
</style>

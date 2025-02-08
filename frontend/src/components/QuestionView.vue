<template>
  <div id="question-view" style="padding: 10px;">
    <div class="title">
      <span>Question View</span>
      <!-- 困难度排序按钮 -->
      <div class="filter difficulty" @click="toggleSortOrder">Difficulty Order:{{ this.sortAscending ? " ↑" : " ↓" }}</div>
      <!-- 下拉菜单筛选知识点 -->
      <Dropdown>
        <!-- trigger element -->
        <template #trigger>
          <button type="button" style="font-weight: bold">
            {{ displayButton }}
          </button>
        </template>
        <!-- contents display in dropdown -->
        <form id="checkboxs" name="myForm">
          <div class="selectK" v-for="(item, index) in uniqueKnowledge" :key="index" style="border-radius: 5px; padding: 5px">
            <input 
              type="checkbox"
              :name="item"
              v-model="selectedKnowledge[item]"
              @change="handleKnowledgeCheck"
            />
            <label
              style="list-style: none;
                     width: 80px;
                     border-bottom: 1px solid #ccc;
                     margin-top: 5px;
                     padding-bottom: 8px;
                     text-align: center;"
            >
              {{ item }}
            </label>
          </div>
          
          <div class="all" style="border-radius: 5px; padding: 5px">
            <input 
              name="all"
              type="checkbox"
              class="knowledge-list"
              v-model="selectAllKnowledge"
              @change="handleSelectAllKnowledge"
            />
            <label 
              for="all"
              style="list-style: none;
                     width: 80px;
                     border-bottom: 1px solid #ccc;
                     margin-top: 5px;
                     padding-bottom: 8px;
                     text-align: center;"
            >
              All
            </label>
          </div>
        </form>
      </Dropdown>
      <div class="filter">Knowledge:</div>
    </div>
    
    <Simplebar style="height: 560px">
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
  components: {
    Simplebar,
    Dropdown
  },
  data() {
    return {
      QuestionData: [],
      uniqueKnowledge: [],
      selectedKnowledge: {},
      selectAllKnowledge: true,
      sortAscending: true // 默认按升序排序
    };
  },
  async mounted() {
    // this.getQuestionData()
  },
  computed: {
    ...mapGetters(['getHadFilter']),
    displayButton() {
      if (this.selectAllKnowledge) return 'All'
      const selectedCount = Object.values(this.selectedKnowledge).filter(Boolean).length
      if (selectedCount > 0) return 'Part'
      else return 'None'
    }
  },
  methods: {
    async getQuestionData() {
      // 获取问题数据
      const { data } = await getQuestions()
      this.QuestionData = data // Flatten the nested structure
      // console.log('Qdata:', data)

      // 获取唯一的 knowledge 类别
      this.uniqueKnowledge = [...new Set(this.QuestionData.map(q => q.knowledge))]
      
      // 初始化 selectedKnowledge 对象
      this.selectedKnowledge = {}
      this.uniqueKnowledge.forEach(knowledge => {
        this.selectedKnowledge[knowledge] = true
      })

      this.renderQuestion()
    },
    // 渲染题目视图数据
    renderQuestion() {
      const d3 = this.$d3
      const width = 650
      const margin = { top: 30, right: 5, bottom: 20, left: 5 }
      const padding = 20
      const innerWidth = width - margin.left - margin.right - padding
      const timelineHeight = 50
      const distributionHeight = 20
      const QuestionTitleHeight = 28
      const QuestionPanelHeight = QuestionTitleHeight + timelineHeight + distributionHeight + padding * 5
      const filteredData = this.QuestionData.filter(q => this.selectedKnowledge[q.knowledge])
      // console.log('Filtered Data:', filteredData)
      // 困难度排序
      if (this.sortAscending) {
        filteredData.sort((a, b) => {
          const diffA = (a.avg_score / a.sum_submit) 
          const diffB = (b.avg_score / b.sum_submit)
          return diffA - diffB
        })
      } else {
        filteredData.sort((a, b) => {
          const diffA = (a.avg_score / a.sum_submit)
          const diffB = (b.avg_score / b.sum_submit)
          return diffB - diffA
        })
      }      
      // 获取可视化目标容器
      const main = d3.select('#visualizationQ')

      // 给容器添加组
      const g = main.append('g')
        .attr('transform', `translate(${margin.left}, ${margin.top})`)

      // 添加题目容器
      // 添加题目容器
      const questionPanel = g.selectAll('.question-panel')
      .data(filteredData)
      .enter()
      .append('svg')
      .attr('width', width)
      .attr('height', QuestionPanelHeight)
      .style('box-shadow', '0px 0px 10px 0px rgba(0,0,0,0.2)')
      .append('g')
      .attr('transform',`translate(${margin.left}, ${0})`)
      .attr('class', 'question-panel')
      .attr('height', QuestionPanelHeight)
      .attr('width', width)

      const qg = questionPanel.append('g')

      // 绘制题目标签
      const labelPadding = 4
      const labelMargin = 10
      const labelContent = ['title_id', 'knowledge'] // 标签内容
      let nowBoxStartPosition = 0
      for(let k = 0; k < labelContent.length; k++) {
        let textElement = qg.append('text') // 添加学生标签
          .attr('x', nowBoxStartPosition)
          .attr('y', padding + QuestionTitleHeight / 2)
          .text(d => `${d[labelContent[k]]}`)
          .attr('font-size', '15px')
          .attr('font-weight', '500')
          .attr('text-anchor', 'start')
        let Bbox = textElement.node() ? textElement.node().getBBox() : {x : 0, y: 0, width: 0, height: 0}
        nowBoxStartPosition += (Bbox.width  + labelMargin + labelPadding * 2) // 更新下一个标签的起始位置
        // console.log('nowBoxStartPosition', nowBoxStartPosition)
        // 添加背景矩形
        qg.insert('rect', ':first-child') // 在第一个子元素之前插入，确保它位于文本下方
          .attr('x', Bbox.x - labelPadding) // 留出一些额外的空间
          .attr('y', Bbox.y - labelPadding)
          .attr('rx', (Bbox.height + labelPadding * 2) / 2) // 圆角半径
          .attr('ry', (Bbox.height + labelPadding * 2) / 2)
          .attr('width', Bbox.width + labelPadding * 2) // 考虑额外空间
          .attr('height', Bbox.height + labelPadding * 2)
          .attr('fill', '#f0f0f0') // 背景颜色
      }

      // 绘制时间轴图图表
      qg.each(function(d) {
        const svg = d3.select(this)
          .attr('width', innerWidth - padding * 2)
          .attr('height', timelineHeight)

        // 添加组
        const tg = svg.append('g')
          .attr('transform', `translate(${margin.left}, ${QuestionTitleHeight + padding * 2})`)
        
        // 定义时间解析器
        const parseTime = d3.timeParse('%Y-%m-%d')

        // 定义缩放尺
        const timelineX = d3.scaleTime()
          .domain(d3.extent(d.timeline, dd => parseTime(dd.date)))
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
          .attr('fill', '#ddd')
          .attr('stroke', 'none')
          .on('mouseover', function() {
            d3.select(this).attr('opacity', 0.5)
          })
          .on('mouseout', function() {
            d3.select(this).attr('opacity', 1)
          })
        
        // 定义坐标轴格式
        const formatTime = d3.timeFormat('%Y/%m/%d')
        // 定义坐标轴
        const xAxis = d3.axisBottom(timelineX)
          .tickFormat(formatTime)
          .ticks(d3.timeWeek.every(2))

        // 添加坐标轴
        tg.append('g').call(xAxis)
          .attr('transform', `translate(0, ${timelineHeight})`)
        d3.selectAll(".tick text")  // 选择所有刻度文本
          .style("fill", "#666")         // 设置为灰色
        
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
                    `)
                    // <p>平均分数:${dd.average_score.toFixed(2)}</p>
              .style('top', `${event.pageY - 28}px`)
              .style('left', `${event.pageX + 10}px`)
          })
          .on('mouseout', function() {
            d3.select(this).attr('r', 2).attr('opacity', 0.2)
            tooltip.style('visibility', 'hidden')
          })
      })

      // 绘制tips
      qg.append('text') // 添加tip标签
          .attr('x', padding / 2)
          .attr('y', QuestionTitleHeight + timelineHeight + padding * 2 - 2)
          .text('Submissions Time Line →')
          .attr('font-size', '12px')
          .attr('font-weight', '300')
          .attr('text-anchor', 'start')
      
      // 添加每一个矩形
      // 绘制分数图像分布
      questionPanel.each(function(d) {
        const svg = d3.select(this)
          .attr('width', innerWidth)
          .attr('height', distributionHeight + margin.top * 2)

        // 为每个分数绘制组
        const scoreG = svg.append('g')
          .attr('transform', `translate(0, ${margin.top + timelineHeight + QuestionTitleHeight + padding * 3})`)

        // 添加 "Score Distribution" 提示文本
        const distribution_textElem = scoreG.append('text')
          .attr('x', 0)
          .attr('y', distributionHeight / 2 - 2)
          .text('Score Distribution:')
          .attr('font-size', '12px')
          .attr('font-weight', '500')
          .attr('text-anchor', 'start')
        const DBbox = distribution_textElem.node().getBBox()
        
        // 定义缩放尺
        const xScale = d3.scaleLinear()
          .domain([0, 100])
          .range([0, innerWidth - DBbox.width])

        // 计算总宽度
        // let totalPercentage = d.distribution.reduce((sum, dist) => sum + dist.percentage, 0)
        let currentWidth = padding / 2

        // 定义颜色比例尺
        const colorScale = d3.scaleSequential(d3.interpolateBlues)
        .domain([-1, d.distribution.length])

        d.distribution.forEach((dist, index) => {
          // 为每个分数创建tooltip
          const tooltip_d = d3.select('body').append('div')
            .attr('class', 'tooltip')
            .style('position', 'absolute')
            .style('visibility', 'hidden') 
            .style('background-color', 'white')
            .style('border', '1px solid black')
            .style('padding', '5px')
          
          // 添加分数标记
          scoreG.append('text')
            .attr('x', DBbox.width + currentWidth + xScale(dist.percentage) / 2)
            .attr('y', distributionHeight / 2)
            .text(`${dist.score}`)
            .attr('font-size', '10px')
            .attr('font-weight', '400')
            .attr('text-anchor', 'middle')
            .attr('dy', '-1em') // Move text slightly above the bar

          // 添加矩形
          scoreG.append('rect')
            .attr('x', DBbox.width + currentWidth)
            .attr('width', xScale(100) - currentWidth) // 需要好好琢磨如何计算
            .attr('height', distributionHeight - 10)
            .attr('fill', colorScale(index))
            .attr('opacity', 0.7)
            .attr('rx', 5)
            .attr('ry', 5)
            .on('mouseover', function(event) {
              d3.select(this).attr('opacity', 0.9)
              tooltip_d.style('visibility', 'visible')
                .html(`<p>Score: ${dist.score}</p>
                      <p>Percentage: ${dist.percentage.toFixed(2)}%</p>`)
                .style('top', `${event.pageY - 28}px`)
                .style('left', `${event.pageX + 10}px`)
            })
            .on('mouseout', function() {
              d3.select(this).attr('opacity', 0.7)
              tooltip_d.style('visibility', 'hidden')
            })

          currentWidth += xScale(dist.percentage)
        })
      })//绘制分数图像分布

      // 绘制棒棒糖图
      const candyStickHeight = 50
      questionPanel.each(function(d) {
        const svg = d3.select(this)
          .attr('width', innerWidth)
          .attr('height', candyStickHeight + margin.top * 2)

        // 为每个棒棒糖绘制组
        const candyG = svg.append('g')
          .attr('transform', `translate(${width * 4 / 5}, ${margin.top + candyStickHeight - padding * 0.5 - 2})`)

        // 定义难度比例尺
        const difficultyScale = d3.scaleThreshold()
          .domain([10, 25, 45, 60]) // 分成四个层级：低、中低、中高、高
          .range(['Expert', 'Hard', 'Medium', 'Easy'])
        // 定义难度高度比例尺
        const stickScale = d3.scaleLinear()
          .domain([50, 0])
          .range([0, candyStickHeight])
        // 定义半径比例尺
        const avgScoreCircleRadius = 25
        const deltaRadius = 5
        const sumSubmitCircleRadius = avgScoreCircleRadius + deltaRadius
        const avgScoreScale = d3.scaleLinear()
          .domain([0, 2])
          .range([1, avgScoreCircleRadius])
        const sumSubmitScale = d3.scaleLinear()
          .domain([d3.min(filteredData, d => d.sum_submit), d3.max(filteredData, d => d.sum_submit)])
          .range([avgScoreCircleRadius, sumSubmitCircleRadius])
        
        // 计算难度值
        const difficultyValue = (d.avg_score * 100 / d.sum_submit) * 100
        const stickHeight = stickScale(difficultyValue)
        // console.log(stickHeight)

        // 创建线性渐变
        const defs = svg.append('defs')
        const linearGradient = defs.append('linearGradient')
          .attr('id', 'gradient-stick')
          .attr('x1', '0%')
          .attr('y1', '0%')
          .attr('x2', '0%')
          .attr('y2', '100%')
        linearGradient.append('stop')
          .attr('offset', '0%')
          .attr('stop-color', '#ffcccb')
          .attr('stop-opacity', 0.8)
        linearGradient.append('stop')
          .attr('offset', '100%')
          .attr('stop-color', '#ff6347')
          .attr('stop-opacity', 0.8)

        // 添加棒子
        candyG.append('rect')
          .attr('class', 'candy-stick')
          .attr('x', -5) // 棒子宽度的一半
          .attr('y', candyStickHeight - stickHeight - sumSubmitCircleRadius)
          .attr('width', 10) // 棒子宽度
          .attr('height', stickHeight + sumSubmitCircleRadius)
          .attr('fill', 'url(#gradient-stick)')

        // 创建tooltip
        const tooltip = d3.select('body').append('div')
          .attr('class', 'tooltip')
          .style('position', 'absolute')
          .style('visibility', 'hidden') 
          .style('background-color', 'white')
          .style('border', '1px solid black')
          .style('padding', '5px')

        // 外圈表示总提交次数
        const outerColor = '#EF9393'
        // const outerColor = '#DF2727'
        candyG.append('circle')
          .attr('cx', 0) // 固定位置
          .attr('cy', candyStickHeight - stickHeight - sumSubmitCircleRadius)
          .attr('r', sumSubmitScale(d.sum_submit))
          .attr('fill', outerColor)
          .attr('opacity', 0.5)
          // .attr('stroke', '#000')
          .attr('stroke-width', 2)
          .on('mouseover', function(event) {
            d3.select(this).attr('fill', outerColor)
            tooltip.style('visibility', 'visible')
              .html(`<p>Total Submissions: ${d.sum_submit}</p>
              <p>Difficulty Level: ${difficultyScale(difficultyValue)}</p>
              `)
              .style('top', `${event.pageY - 28}px`)
              .style('left', `${event.pageX + 10}px`)
          })
          .on('mouseout', function() {
            d3.select(this).attr('fill', outerColor)
            tooltip.style('visibility', 'hidden')
          })

          // 内圈表示平均分数
          // const innerColor = '#D62728'
          const innerColor = '#AD0000'
          candyG.append('circle')
          .attr('cx', 0) // 固定位置
          .attr('cy', candyStickHeight - stickHeight - avgScoreCircleRadius - deltaRadius)
          .attr('r', avgScoreScale(d.avg_score))
          .attr('fill', innerColor)
          .attr('opacity', 0.5)
          // .attr('stroke', '#000')
          .attr('stroke-width', 2)
          .on('mouseover', function(event) {
            d3.select(this).attr('fill', '#ff6347')
            tooltip.style('visibility', 'visible')
            .html(`<p>Average Score: ${d.avg_score.toFixed(2)}</p>
              <p>Difficulty Level: ${difficultyScale(difficultyValue)}</p>
              `)
              .style('top', `${event.pageY - 28}px`)
              .style('left', `${event.pageX + 10}px`)
          })
          .on('mouseout', function() {
            d3.select(this).attr('fill', innerColor)
            tooltip.style('visibility', 'hidden')
          })
      })
    },
    handleKnowledgeCheck() {
      this.selectAllKnowledge = Object.values(this.selectedKnowledge).every(Boolean)
      const d3 = this.$d3
      d3.select('#visualizationQ').selectAll('*').remove()
      // 重新渲染图表
      this.renderQuestion()
    },
    handleSelectAllKnowledge() {
      Object.keys(this.selectedKnowledge).forEach(key => {
        this.selectedKnowledge[key] = this.selectAllKnowledge
      })
      const d3 = this.$d3
      d3.select('#visualizationQ').selectAll('*').remove()
      // 重新渲染图表
      this.renderQuestion()
    },
    toggleSortOrder() {
      this.sortAscending = !this.sortAscending
      const d3 = this.$d3
      d3.select('#visualizationQ').selectAll('*').remove()
      // 重新渲染图表
      this.renderQuestion()
    }
  },
  watch: {
    getHadFilter() {
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
    padding-bottom: 4px;
    span {
      font-size: 20px;
      font-weight: bold;
      padding-bottom: 10px;
      margin-bottom: 20px;
      padding-left: 10px;
    }
    .filter {
      float: right;
      cursor: pointer;
      font-weight: bold;
      font-size: 18px;
      padding-right: 10px;
    }
    .difficulty{
      margin-left: 20px;
    }
    .v-dropdown-trigger {
      float: right;
      button {
        border: 0;
        margin-top: 5px;
        margin-right: 5px;
        background-color: #fff;
        padding: 0;
      }
    }
  }
  
}
.highlight {
  color: #3b82f6;
}
.candy-stick {
  fill: url(#gradient-stick);
}
</style>
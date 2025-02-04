<template>
  <div class="scrollBarWrap" id="student-view" data-simplebar>
    <div class="title">
      <span>Student View</span>
      <input class="limit-input" type="number" v-model="limitLength" @change="updateLimit" />
      <div class="filter">Limit: </div>
    </div>
    <Simplebar style="height: 1170px">
      <div id="visualizationS"></div>
    </Simplebar>
  </div>
</template>

<script>
import { mapGetters } from 'vuex'
import { getStudents } from '@/api/StudentView'
import Simplebar from 'simplebar-vue'
import 'simplebar-vue/dist/simplebar.min.css'

export default {
  name: 'StudentView',
  components: {
    Simplebar
  },
  data() {
    return {
      treeData: [], // 树形数据
      currentCluster: null, // 当前集群
      limitLength: 10, // 显示的学生数量限制
      factLength: null, // 实际的学生数量
      PanelsHeight: [], // 面板高度
    }
  },
  computed: {
    ...mapGetters(['getHadFilter', 'getColors']), // 从 Vuex 获取过滤状态和颜色
    JustClusterData() {
      return this.$store.state.justClusterData // 从 Vuex 获取集群数据
    },
  },
  async created() {
    await this.getTreeData() // 初始化时获取学生数据并渲染
  },
  methods: {
    async getTreeData() {
      const { data: { children } } = await getStudents() // 获取学生树形数据
      console.log('studentData', children)
      this.treeData = children
      this.renderEveryStudents() // 渲染所有学生
    },

    renderQuestions(svg, questions, th) {
      if (!questions || questions.length === 0) return // 如果没有问题，直接返回

      const d3 = this.$d3
      const lineLength = 120        // 连接线长度
      const radius = 3              // 节点半径
      const studentTitleHeight = 30 // 学生标题高度
      const studentTipHeight = 40 // 学生提示高度
      let xOffset = 0 // 纵向偏移量

      const treeParam = { 
        width: 40,   // 横向长度
        height: 20,  //纵向长度
        allotHeight: 75,  //预留纵向长度
        margin: 30,  // 树形布局边距
       } // 树形布局边距

      // 渲染单个问题的方法
      const renderQuestion = (g, tree) => {
        const currentColor = this.getColors[this.currentCluster] // 获取当前集群的颜色

        g.selectAll('path').data(tree.links()).join('path') // 绘制连接线
          .attr('fill', 'none')
          .attr('stroke', currentColor)
          .attr('d', d3.linkHorizontal().x(d => d.y).y(d => d.x))

        g.selectAll('line').data(tree.descendants()).join('line') // 绘制水平线
          .attr('x1', 0)
          .attr('x2', 50)
          .attr('y1', 20)
          .attr('y2', 20)

        g.selectAll('.base-line').data(tree.descendants()).join('rect') // 绘制基础线条
          .attr('class', 'base-line')
          .attr('x', d => d.y)
          .attr('y', d => d.x - radius / 2)
          .attr('width', d => d.children ? 0 : lineLength)
          .attr('height', 3)
          .attr('fill', currentColor)
          .attr('opacity', 0.5)
          .attr('rx', 2)
          .attr('ry', 2)

        const maxTimes = d3.max(tree.descendants(), dd =>dd.data.times)
        g.selectAll('circle').data(tree.descendants()).join('circle') // 绘制节点
          .attr('cx', d => d.y + d.data.times * lineLength / (maxTimes * 1.2))
          .attr('cy', d => d.x)
          .attr('r', d => d.children ? 0 : radius)
          .attr('fill', currentColor)

        g.selectAll('text').data(tree.descendants()).join('text') // 绘制文本,d.children区分知识点和问题节点
          .attr('x', d => d.y + (d.children ? -radius - 5  : radius + 5))
          .attr('y', d => d.x + radius / 2 - (d.children ? 0 : radius * 3 / 2))
          .text(d => d.data.name)
          .attr('font-size', '10px')
          .attr('text-anchor', d => d.children ? 'end' : 'start')

        g.selectAll('.score-line').data(tree.descendants()).join('rect') // 绘制分数线条
          .attr('class', 'score-line')
          .attr('x', d => d.y + radius + lineLength)
          .attr('y', d => d.x - radius / 2)
          .attr('width', d => (d.data.value ? d.data.value : 0) * lineLength / 5)
          .attr('height', 5)
          .attr('fill', currentColor)
          .attr('rx', 2)
          .attr('ry', 2)
      }

      const margin = { top: 20, right: 20, bottom: 20, left: 50 } // 边距
      
      questions.forEach((q) => {
        q.name = q.name.slice(-5) // 截取问题名称的最后5个字符
        
        const root = d3.hierarchy(q) // 创建层次结构
        const treeLayout = d3.tree()
        .nodeSize([treeParam.height, treeParam.width]) // 定义树形布局
        const tree = treeLayout(root)
        
        // 计算当前树的尺寸
        const nodes = root.descendants()
        const minX = d3.min(nodes, d => d.x)
        const maxX = d3.max(nodes, d => d.x)
        const treeWidth = maxX - minX


        const qg = svg.append('g') // 创建一个新的组
        .attr('transform', `translate(${margin.left}, ${xOffset - minX + studentTitleHeight + studentTitleHeight})`)
        
        renderQuestion(qg, tree) // 渲染问题
        // 更新水平偏移量
        xOffset += treeWidth + treeParam.margin // 树宽度 + 间距
      })// questions.forEach
      this.PanelsHeight[th] = xOffset + margin.top + studentTitleHeight + studentTipHeight
    },

    renderEveryStudents() {
      const d3 = this.$d3
      // const titleHeight = 20 // 标题高度
      const width = 390 // SVG 宽度
      const height = 100 // SVG 高度
      const studentTitleHeight = 30 // 学生标题高度
      const labelPadding = 5 // 标签高度
      const margin = { top: 20, right: 20, bottom: 10, left: 20 } // 边距
      const padding = { top: 0, right: 10, bottom: 10, left: 5 } // 内边距
      const studentTipHeight = 40 // 学生提示高度
      const tipBlockWidth = (width - margin.right - margin.left) / 3 // 提示块宽度
      const tipContent = ['Knowledge', 'State', 'Score'] // 提示内容

      const svg = d3.select('#visualizationS') // 选择 SVG 元素
        .attr('width', width)
        .attr('height', height)

      svg.selectAll('*').remove() // 清除之前的 SVG 元素

      const g = svg.append('g') // 创建一个新的组
      
      this.factLength = this.treeData.length // 设置实际的学生数量
      this.PanelsHeight = new Array(this.factLength).fill(0) // 初始化学生面板高度数组
      this.treeData.forEach((s, i) => {
        if (i >= this.limitLength) return // 如果超过限制，跳过
        
        this.currentCluster = this.JustClusterData[s.name] // 设置当前集群
        const studentPanelHeight = studentTitleHeight + studentTipHeight + margin.bottom // 计算学生面板高度
        const varUpdateFunc = this.updatePanelHeight
        const studentPanel = g.append('svg') // 创建学生面板
          .attr('transform', `translate(${margin.left}, ${0})`)
          .attr('class', 'student-panel')
          .attr('width', width - margin.left - margin.right)
          .attr('height', studentPanelHeight)
          .attr('y', (d, ii) => ii * studentPanelHeight + studentTitleHeight)
          .style('box-shadow', '0 0 10px rgba(0, 0, 0, 0.1)')
          .on("mouseover", function() {
            // 鼠标移入时，高度变为 xxpx（带过渡动画）
            varUpdateFunc(d3.select(this), i)
          })
          .on("mouseout", function() {
            // 鼠标移出时，恢复为 30px（带过渡动画）
            d3.select(this)
              .transition()
              .duration(700)
              .attr("height", studentPanelHeight)
          })
        const sg = studentPanel.append('g') // 创建一个新的组
          .attr('transform', `translate(${margin.left}, ${studentTitleHeight})`)

          let textNameElement = sg.append('text') // 添加学生标签
          .attr('x', padding.left)
          .attr('y', padding.top)
          .text('S-' + s.name)
          .attr('font-size', '12px')
          .attr('font-weight', '600')
          .attr('text-anchor', 'start')
          let textClassElement = sg.append('text') // 添加major标签
          .attr('x', padding.left + tipBlockWidth*2)
          .attr('y', padding.top)
          .text(s.class)
          .attr('font-size', '12px')
          .attr('font-weight', '600')
          .attr('text-anchor', 'start')

        // 获取文本元素的尺寸
        let nameBbox = textNameElement.node().getBBox()
        let classBbox = textClassElement.node().getBBox()
        // 添加背景矩形
        sg.insert('rect', ':first-child') // 在第一个子元素之前插入，确保它位于文本下方
          .attr('x', nameBbox.x - labelPadding) // 留出一些额外的空间
          .attr('y', nameBbox.y - labelPadding)
          .attr('rx', (nameBbox.height + labelPadding * 2) / 2) // 圆角半径
          .attr('ry', (nameBbox.height + labelPadding * 2) / 2)
          .attr('width', nameBbox.width + labelPadding * 2) // 考虑额外空间
          .attr('height', nameBbox.height + labelPadding * 2)
          .attr('fill', '#f0f0f0') // 背景颜色
        // 添加背景矩形
        sg.insert('rect', ':first-child') // 在第一个子元素之前插入，确保它位于文本下方
          .attr('x', classBbox.x - labelPadding) // 留出一些额外的空间
          .attr('y', classBbox.y - labelPadding)
          .attr('rx', (classBbox.height + labelPadding * 2) / 2) // 圆角半径
          .attr('ry', (classBbox.height + labelPadding * 2) / 2)
          .attr('width', classBbox.width + labelPadding * 2) // 考虑额外空间
          .attr('height', classBbox.height + labelPadding * 2)
          .attr('fill', '#f0f0f0') // 背景颜色

        // 注意: 如果你希望背景矩形和文本保持一致的位置和变换，确保它们都应用相同的transform属性。

          for(let t = 0; t < 3; t++){
            sg.append('text') // 添加tip标签
            .attr('x', padding.left + tipBlockWidth * t)
            .attr('y', padding.top + studentTitleHeight)
            .text(tipContent[t])
            .attr('font-size', '12px')
            .attr('font-weight', '300')
            .attr('text-anchor', 'start')
          }


        const Questions = s.children // 获取学生的问题
        console.log('i', i)
        this.renderQuestions(sg, Questions, i) // 渲染问题
      })
    },

    updateLimit() {
      if (this.limitLength > this.factLength) {
        this.limitLength = this.factLength // 如果超过实际数量，设置为实际数量
        return
      }
      if (this.limitLength < 1) {
        this.limitLength = 1 // 如果小于1，设置为1
        return
      }
      this.renderEveryStudents() // 更新限制后重新渲染
    },
    updatePanelHeight(element, index) {
      element
      .transition()
      .duration(300)  // 动画时长 300ms
      .attr("height", this.PanelsHeight[index])
    }
  },
  watch: {
    getHadFilter() {
      this.renderEveryStudents()
    }
  }
}
</script>

<style scoped lang="less">
#student-view {
  width: 395px;
  height: 1220px;
  border-radius: 5px;
  background-color: #fff;
  .title {
    font-size: 20px;
    font-weight: bold;
    margin-left: 10px;
    margin-top: 10px;
    padding: 5px;
    padding-top: 0;
    border-bottom: 1px solid #ccc;
    .filter {
      float: right;
      margin-right: 5px;
    }
    .limit-input {
      float: right;
      width: 30px;
      height: 22px;
      text-align: center;
      line-height: 12px;
      margin-right: 10px;
      padding-left: 17px;
      border: 0;
      font-weight: bold;
      border-bottom: 1px solid #000;
    }
  }
  .student-panel {
    box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
    cursor: pointer;
    /*超出页面增加滚动效果*/
    overflow: scroll;
  }
}
/deep/ .simplebar-vertical {
  width: 16px;
}
</style>




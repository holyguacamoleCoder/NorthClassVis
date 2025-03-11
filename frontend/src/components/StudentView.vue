<template>
  <div class="scrollBarWrap" id="student-view" data-simplebar ref="scrollContainer">
    <div class="title">
      <span>Student View</span>
      <select class="filter-input" v-model="selectedMajor" @change="applyFilter">
        <option value="">All</option>
        <option v-for="major in uniqueMajors" :key="major">{{ major }}</option>
      </select>
      <div class="filter">Major:</div>
    </div>
    <Simplebar style="height: 1160px" @scroll="handleScroll">
      <div id="visualizationStu" ref="visualizationStu">
        <div class="wait-prompt"  v-if="isWaiting">Waiting for brush :) ...</div>
        <LoadingSpinner v-if="loading" />
      </div>
    </Simplebar>
  </div>
</template>

<script>
import { mapState, mapGetters } from 'vuex'
import { getStudents } from '@/api/StudentView'
import Simplebar from 'simplebar-vue'
import 'simplebar-vue/dist/simplebar.min.css'
import LoadingSpinner from './LoadingSpinner.vue'

export default {
  name: 'StudentView',
  components: {
    Simplebar,
    LoadingSpinner
  },
  data() {
    return {
      debugger: true,
      isWaiting: true,
      loading: false, // 加载状态
      treeData: [], // 树形数据
      currentCluster: null, // 当前集群
      selectedMajor: '', // 选中的专业
      factLength: null, // 实际的学生数量
      PanelsHeight: [], // 面板高度
      visibleIndices: new Set(), // 可见的学生索引集合
      expandedIndices: new Set(), // 展开的学生索引集合
      batchSize: 20, // 每次加载的数量
      uniqueMajors: [] // 唯一的专业列表
    }
  },
  computed: {
    ...mapState(['configLoaded']),
    ...mapGetters(['getStudentClusterInfo','getSelectedIds', 'getSelectedData','getColors']),
    filteredTreeData() {
      if (!this.selectedMajor) return this.treeData
      return this.treeData.filter(student => student.major === this.selectedMajor)
    }
  },
  async created() {
    
  },
  mounted() {
  },
  methods: {
    async getTreeData(stu_ids) {
      const { data: { children } } = await getStudents(stu_ids) // 获取学生树形数据
      // console.log('studentData', children)
      // 筛选出选中的学生数据
      this.treeData = children
      this.factLength = children.length // 设置实际的学生数量
      this.PanelsHeight = new Array(this.factLength).fill(0) // 初始化学生面板高度数组
      this.uniqueMajors = [...new Set(children.map(student => student.major))] // 获取唯一的专业列表
    },

    renderQuestions(svg, questions, th) {
      if (!questions || questions.length === 0) return // 如果没有问题，直接返回

      const d3 = this.$d3
      const lineLength = 120        // 连接线长度
      const radius = 3              // 节点半径
      const studentTitleHeight = 30 // 学生标题高度
      const studentTipHeight = 40   // 学生提示高度
      let xOffset = 0               // 纵向偏移量

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

        const maxTimes = d3.max(tree.descendants(), dd => dd.data.times)
        g.selectAll('circle').data(tree.descendants()).join('circle') // 绘制节点
          .attr('cx', d => d.y + d.data.times * lineLength / (maxTimes * 1.2))
          .attr('cy', d => d.x)
          .attr('r', d => d.children ? 0 : radius)
          .attr('fill', currentColor)

        g.selectAll('text').data(tree.descendants()).join('text') // 绘制文本,d.children区分知识点和问题节点
          .attr('x', d => d.y + (d.children ? -radius - 5 : radius + 5))
          .attr('y', d => d.x + radius / 2 - (d.children ? 0 : radius * 3 / 2))
          .text(d => d.data.name)
          .attr('font-size', '10px')
          .attr('text-anchor', d => d.children ? 'end' : 'start')

        g.selectAll('.score-line').data(tree.descendants()).join('rect') // 绘制分数线条
          .attr('class', 'score-line')
          .attr('x', d => d.y + radius + lineLength)
          .attr('y', d => d.x - radius)
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

    loadStudentPanel(index) {
      if (this.visibleIndices.has(index)) return // 如果已经加载过，则跳过

      const d3 = this.$d3
      const width = 440 // SVG 宽度
      const studentTitleHeight = 30 // 学生标题高度
      const labelPadding = 5 // 标签内边距
      const labelMargin = 20 // 标签外边距
      const labelContent = ['name', 'class', 'major'] // 标签内容
      const margin = { top: 20, right: 20, bottom: 10, left: 20 } // 边距
      const padding = { top: 5, right: 10, bottom: 10, left: 5 } // 内边距
      const studentTipHeight = 40 // 学生提示高度
      const tipBlockWidth = (width - margin.right - margin.left) / 3 // 提示块宽度
      const tipContent = ['Knowledge', 'State', 'Score'] // 提示内容

      const svg = d3.select('#visualizationStu') // 选择 SVG 元素

      const g = svg.append('g') // 创建一个新的组
      
      const s = this.filteredTreeData[index]
      
      this.currentCluster = this.getStudentClusterInfo[s.name] // 设置当前集群
      const studentPanelHeight = studentTitleHeight + studentTipHeight + margin.bottom // 计算学生面板高度
      const varToggleFunc = this.togglePanelHeight
      const studentPanel = g.append('svg') // 创建学生面板
        .attr('transform', `translate(${margin.left}, ${0})`)  
        .attr('class', 'student-panel')
        .attr('width', width - margin.left - margin.right)
        .attr('height', studentPanelHeight)
        // .attr('height', this.PanelsHeight[index])
        .style('box-shadow', '0 0 10px rgba(0, 0, 0, 0.1)')
        .on("click", function() {
          // 点击时，切换面板的高度
          varToggleFunc(d3.select(this), index)
        })

      const sg = studentPanel.append('g') // 创建一个新的组
        .attr('transform', `translate(${margin.left}, ${studentTitleHeight})`)

      let nowBoxStartPosition = 0
      for(let k = 0; k < labelContent.length; k++) {
        let textElement = sg.append('text') // 添加学生标签
          .attr('x', padding.left + nowBoxStartPosition)
          .attr('y', padding.top)
          .text(s[labelContent[k]])
          .attr('font-size', '12px')
          .attr('font-weight', '600')
          .attr('text-anchor', 'start')
        let Bbox = textElement.node().getBBox()
        nowBoxStartPosition += (Bbox.width  + labelMargin + labelPadding * 2) // 更新下一个标签的起始位置
        // console.log('nowBoxStartPosition', nowBoxStartPosition)
        // 添加背景矩形
        sg.insert('rect', ':first-child') // 在第一个子元素之前插入，确保它位于文本下方
          .attr('x', Bbox.x - labelPadding) // 留出一些额外的空间
          .attr('y', Bbox.y - labelPadding)
          .attr('rx', (Bbox.height + labelPadding * 2) / 2) // 圆角半径
          .attr('ry', (Bbox.height + labelPadding * 2) / 2)
          .attr('width', Bbox.width + labelPadding * 2) // 考虑额外空间
          .attr('height', Bbox.height + labelPadding * 2)
          .attr('fill', '#f0f0f0') // 背景颜色
      }

      for(let t = 0; t < tipContent.length; t++){
        sg.append('text') // 添加tip标签
          .attr('x', padding.left + tipBlockWidth * t)
          .attr('y', padding.top + studentTitleHeight)
          .text(tipContent[t])
          .attr('font-size', '17px')
          .attr('font-weight', '300')
          .attr('text-anchor', 'start')
      }

      const Questions = s.children // 获取学生的问题
      this.renderQuestions(sg, Questions, index) // 渲染问题

      this.visibleIndices.add(index) // 标记为已加载
    },

    loadInitialBatch() {
      for (let i = 0; i < Math.min(this.batchSize, this.filteredTreeData.length); i++) {
        this.loadStudentPanel(i)
      }
    },

    handleScroll() {
      const container = this.$refs.scrollContainer.querySelector('.simplebar-content-wrapper')
      const scrollPosition = container.scrollTop
      const containerHeight = container.clientHeight
      // const totalHeight = container.scrollHeight

      const panelHeight = 100 // 假设每个面板的高度为80px，可以根据实际情况调整

      const startIdx = Math.floor(scrollPosition / panelHeight)
      const endIdx = Math.ceil((scrollPosition + containerHeight) / panelHeight)

      for (let i = startIdx; i <= endIdx && i < this.filteredTreeData.length; i++) {
        this.loadStudentPanel(i)
      }
    },

    togglePanelHeight(element, index) {
      const targetHeight = this.expandedIndices.has(index) ? 80 : this.PanelsHeight[index]
      element
        .transition()
        .duration(400)  // 动画时长 300ms
        .attr("height", targetHeight)
      
      if (this.expandedIndices.has(index)) {
        this.expandedIndices.delete(index)
      } else {
        this.expandedIndices.add(index)
      }
    },

    applyFilter() {
      this.visibleIndices.clear() // 清空可见索引集合并重新加载
      this.expandedIndices.clear() // 清空展开索引集合并重新加载
      this.$refs.visualizationStu.innerHTML = '' // 清空现有内容
      this.loadInitialBatch() // 重新加载初始批次的数据
    },
    async loadData(render = true) {
      this.loading = true
      this.visibleIndices.clear() // 清空可见索引集合并重新加载
      this.expandedIndices.clear() // 清空展开索引集合并重新加载
      this.$refs.visualizationStu.innerHTML = '' // 清空现有内容
      if(render){
        await this.getTreeData(this.getSelectedIds) // 初始化时获取学生数据
        this.loadInitialBatch() // 重新加载初始批次的数据
      }
      this.loading = false
    }
  },
  watch: {
    configLoaded(newVal) {
      if (newVal) {
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
    }
  }
}
</script>

<style scoped lang="less">
#student-view {
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
      font-size: 17px;
      font-weight: 400;
    }
    .filter-input {
      float: right;
      width: 100px;
      height: 26px;
      margin-right: 10px;
      border: 1px solid #ccc;
      border-radius: 4px;
      padding: 2px;
      font-size: 14px;
    }
    .filter{
      font-weight: bold;
    }
  }
  .wait-prompt{
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translateX(-50%) translateY(-50%);;
    font-size: 30px;
    font-weight: bold;
    color: #eee;
  }
  .student-panel {
    box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
    cursor: pointer;
    /*超出页面增加滚动效果*/
    overflow-y: scroll;
  }
}
/deep/ .simplebar-vertical {
  width: 16px;
}
</style>




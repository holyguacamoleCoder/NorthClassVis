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
      treeData: [],
      currentCluster: null,
      limitLength: 3,
      // colors:['#ff7f00', '#377eb8', '#4daf4a'],
      factLength: null
    }
  },
  computed: {
    ...mapGetters(['getHadFilter', 'getColors']),
    JustClusterData(){
      return this.$store.state.justClusterData
    },
  },
  async created(){
    this.getTreeData()
  },
  async mounted() {
  },
  updated() {
    // console.log(this.$refs.studentContainer)
  },
  methods: {
    async getTreeData() {
      // 获取学生树形数据
      const { data: { children } }  = await getStudents()
      console.log('studentData',children)
      this.treeData = children
      this.renderEveryStudents()
    },

    renderQuestions(Questions, sg){
      // console.log('renderTree')
      if(!Questions || Questions.length === 0) return

      const d3 = this.$d3
      const lineLength = 100
      const radius = 5
      const treeWidth = 75
      const currentColor = this.getColors[this.currentCluster]
      const studentTitleHeight = 30

      
      // 渲染函数
      const render = (g, tree) => {
        g.selectAll('path').data(tree.links()).join('path')
        .attr('fill', 'none')
        .attr('stroke', `${currentColor}`)
        .attr('d', d3.linkHorizontal().x(d => d.y).y(d => d.x))
        // 树的连接线
        g.selectAll('line').data(tree.descendants()).join('line')
        .attr('x1', 0)
        .attr('x2', 50)
        .attr('y1', 20)
        .attr('y2', 20)
         // 此次提交分数
         g.selectAll('.base-line').data(tree.descendants()).join('rect')
        .attr('class', 'base-line')
        .attr('x', d => d.y)
        .attr('y', d => d.x - radius / 2 + 1)
        .attr('width', d => d.children ? 0 : lineLength)
        .attr('height', 3)
        .attr('fill', `${currentColor}`)
        .attr('opacity', 0.5)
        .attr('rx', 2)
        .attr('ry', 2)
        // 节点
        g.selectAll('circle').data(tree.descendants()).join('circle')
        .attr('cx', d => d.y + d.data.times * 8)
        .attr('cy', d => d.x)
        .attr('r', radius)
        .attr('fill', `${currentColor}`)
        // 题目提交状态
        g.selectAll('text').data(tree.descendants()).join('text')
        .attr('x', d => d.y + (d.children ? -radius - 1 : radius + 5))
        .attr('y', d => d.x + radius / 2 - radius * 3 / 2)
        .text(d => d.data.name)
        .attr('font-size', '10px')
        .attr('text-anchor', d => d.children ? 'end' : 'start') 
        // 此次提交分数
        g.selectAll('.score-line').data(tree.descendants()).join('rect')
        .attr('class', 'score-line')
        .attr('x', d => d.y + radius + lineLength)
        .attr('y', d => d.x - radius / 2)
        .attr('width', d => (d.data.value ? d.data.value : 0) * 10) // 假设 values 是数值类型
        .attr('height', 5)
        .attr('fill', `${currentColor}`)
        .attr('rx', 2)
        .attr('ry', 2)
      }

      // 为每棵树创建一个g------------------------
      const margin = { top: 20, right: 20, bottom: 20, left: 100 }
      Questions.forEach((q, i) => {
        // 为每棵树定义一个组
        // console.log('q',q)
        q.name = q.name.slice(-5)
        const qg = sg.append('g')
        .attr('transform', `translate(${margin.left}, ${treeWidth * i + studentTitleHeight})`)
        
        const root = d3.hierarchy(q)
        // 定义一个树形布局,并映射为具体位置
        const tree = d3.tree()
              .size([70, 70])(root)
        render(qg,tree)
      })
      

    },

    renderEveryStudents(){
      // console.log('renderEveryStudents')
      const d3 = this.$d3
      const titleHeight = 20
      const width = 390
      const height = 100
      const studentTitleHeight = 20
      const treeWidth = 80
      const margin = { top: 20, right: 20, bottom: 20, left: 20 }
      const svg = d3.select('#visualizationS')
        .attr('width', width)
        .attr('height', height)

      const g = svg.append('g')
        .attr('transform', `translate(${margin.left}, ${margin.top + titleHeight})`)
      
      // 对应了1个学生
      this.factLength = this.treeData.length

      // this.treeData.length = 2
      this.treeData.forEach((s, i) => {
        if(i >= this.limitLength) return

        // console.log('s',s)
        this.currentCluster = this.JustClusterData[s.name]
        // console.log('this.currentCluster',this.currentCluster)
        // 创建学生画布
        const studentPanelHeight = studentTitleHeight + treeWidth * s.children.length
        const studentPanel = g.append('svg')
            .attr('class', 'student-panel')
            .attr('width', width - margin.left - margin.right + 30)
            .attr('height', studentPanelHeight)
            .attr('x', '60')
            .attr('y', (d, i) => i * studentPanelHeight + studentTitleHeight)
            .style('box-shadow', '0 0 10px rgba(0, 0, 0, 0.1)')
        const sg = studentPanel.append('g')
              .attr('transform', `translate(${margin.left}, ${studentTitleHeight})`)
        // 给每个学生打上标签
        sg.append('text')
          .attr('x', 10)
          .attr('y', 10)
          .text('Student-' + s.name)
          .attr('font-size', '17px')
          .attr('font-weight', 'bold')
          .attr('text-anchor', 'start') 
        
        // 遍历这个s的所有问题
        const Questions = s.children
        // console.log('Questions',Questions)
        // 每个问题对应一棵树，我们渲染它 
        this.renderQuestions(Questions, sg)
      }) // forEach-s
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
      d3.select('#visualizationS').selectAll('*').remove()
      // 重新渲染图表
      
      this.renderEveryStudents()
    }
  },//methods
  watch: {
    getHadFilter(){
      console.log('had filter change!!SSS')
      this.$d3.select('#visualizationS').selectAll('*').remove()
      this.getTreeData()
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
  .title{
    font-size: 20px;
    font-weight: bold;
    margin-left: 10px;
    margin-top: 10px;
    padding: 5px;
    padding-top: 0;
    border-bottom: 1px solid #ccc;
    .filter{
      float: right;
      margin-right:5px;
    }
    .limit-input{
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
  .student-panel{
    box-shadow:0 0 10px rgba(0, 0, 0, 0.1);
  }
}
/deep/ .simplebar-vertical {
  width: 16px;
}
</style>

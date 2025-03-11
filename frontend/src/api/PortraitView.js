import request from '@/utils/request'

// 获取距离聚类中心最近坐标的学生数据
export const getClusterStudents = () => {
  return request.get('/cluster/students')
}
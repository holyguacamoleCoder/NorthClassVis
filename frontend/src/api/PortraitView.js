import request from '@/utils/request'
import throttle from '@/utils/throttle'
// 获取周视图相关数据
export const getClusterStudents = throttle(() => {
  return request.get('/cluster/students')
})
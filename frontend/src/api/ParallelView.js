import request from '@/utils/request'

// 获取每一个学生的坐标和类
export const getClusterEveryone = () => {
  return request.get('/cluster/everyone', {
    params:{
    }
  })
}
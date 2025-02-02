import request from '@/utils/request'

// 获取周视图相关数据
export const getWeeks = () => {
  return request.get('/week')
}

export const getClusters = () => {
  return request.get('/cluster', {
    params:{
      every: true
    }
  })
}



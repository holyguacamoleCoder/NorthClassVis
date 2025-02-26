import request from '@/utils/request'
import throttle  from '@/utils/throttle'
// 获取周视图相关数据
export const getClusterEveryone = throttle(() => {
  return request.get('/cluster/everyone', {
    params:{
    }
  })
})
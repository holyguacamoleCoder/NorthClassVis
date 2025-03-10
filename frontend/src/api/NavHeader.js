import request from '@/utils/request'

// 获取周视图相关数据
export const getSelectedData = (brushedStudent) => {
  return request.get('/cluster/select', { 
    params: {
      brushedStudent
    } 
  })
}
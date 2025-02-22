import request from '@/utils/request'

// 获取周视图相关数据
export const getWeeks = () => {
  return request.get('week/week_data')
}



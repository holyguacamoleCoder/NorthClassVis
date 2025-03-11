import request from '@/utils/request'

// 获取周视图相关数据
export const getWeeks = (selectedIds) => {
  return request.get('week/week_data', selectedIds ? {
    params: {
      student_ids: selectedIds
    }
  } : null)
}



import request from '@/utils/request'

// 获取周视图相关数据
export const getWeeks = (selectedIds) => {
  return request.get('week/week_data', selectedIds ? {
    params: {
      student_ids: selectedIds
    }
  } : null)
}


export const getPeaks = (selectedIds, day = 5) => {
  return request.get('week/peak_data', selectedIds ? {
    params: {
      student_ids: selectedIds,
      day: day
    }
  } : null)
}

import request from '@/utils/request'

// 获取周视图相关数据；weekRange 为 [start, end] 周次（与 Nav / Agent 右栏一致）
export const getWeeks = (selectedIds, weekRange = null) => {
  const params = {}
  if (selectedIds?.length) params.student_ids = selectedIds
  if (weekRange && Array.isArray(weekRange) && weekRange.length >= 2) {
    params.week_start = Number(weekRange[0])
    params.week_end = Number(weekRange[1])
  }
  return Object.keys(params).length
    ? request.get('week/week_data', { params })
    : request.get('week/week_data')
}

export const getPeaks = (selectedIds, day = 5, weekRange = null) => {
  const params = { day }
  if (selectedIds?.length) params.student_ids = selectedIds
  if (weekRange && Array.isArray(weekRange) && weekRange.length >= 2) {
    params.week_start = Number(weekRange[0])
    params.week_end = Number(weekRange[1])
  }
  return request.get('week/peak_data', { params })
}

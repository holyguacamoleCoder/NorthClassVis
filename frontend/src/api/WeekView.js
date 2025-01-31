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

// // 登录接口
// export const loginCode = (mobile, smsCode) => {
//   return request.post('/passport/login', {
//     form: {
//       isParty: false,
//       partyData: {},
//       mobile,
//       smsCode
//     }
//   })
// }

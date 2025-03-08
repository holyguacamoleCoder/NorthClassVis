import request from '@/utils/request'
// import debounce from '@/utils/debounce'
// import throttle from '@/utils/throttle'
export const setConfig = (CheckoutClasses, CheckoutMajors) => {
  return request.post('/nav/config', {
    classes: CheckoutClasses,
    majors: CheckoutMajors
  })
}

export const getConfig = () => {
  return request.get('/nav/filter')
}
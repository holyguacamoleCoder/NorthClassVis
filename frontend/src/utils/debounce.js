const defaultWait = 3000;

function debounce(func, wait = defaultWait) {
  let timeout = null;

  return function(...args) {
    const context = this;

    // 清除之前的定时器
    if (timeout) {
      clearTimeout(timeout);
    }

    // 设置新的定时器
    timeout = setTimeout(() => {
      func.apply(context, args);
    }, wait);
  };
}

export default debounce;
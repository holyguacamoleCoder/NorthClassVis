const defaultWait = 30000;
function throttle(func, wait=defaultWait) {
  let timeout = null;
  let lastArgs = null;
  let lastThis = null;
  let lastCallTime = 0;
  let lastResult = null;

  function later() {
    lastCallTime = Date.now();
    timeout = null;
    lastResult = func.apply(lastThis, lastArgs);
    lastArgs = lastThis = null;
    return lastResult;
  }

  return function(...args) {
    const now = Date.now();
    const remainingTime = wait - (now - lastCallTime);

    lastArgs = args;
    lastThis = this;

    if (remainingTime <= 0 || remainingTime > wait) {
      if (timeout) {
        clearTimeout(timeout);
        timeout = null;
      }
      lastCallTime = now;
      lastResult = func.apply(this, args);
      return lastResult;
    } else if (!timeout) {
      timeout = setTimeout(later, remainingTime);
      return lastResult || Promise.resolve(); // 返回一个空的 Promise 以保持一致性
    }
  };
}

export default throttle;
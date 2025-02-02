# 0. 性能记录方法（粗略）

  1. 前端渲染时间：
    主要记录渲染函数耗时，利用performance.now()记录渲染开始和结束时间，计算差值
    暂时没有单独设计回调函数
    ```js
    // 渲染函数
    initChart(){
      const start = performance.now()
      setTimeout(() => {
        // 模拟渲染逻辑
      }, 10)
      const end = performance.now()
      console.log(`ParallelView Render time: ${endTime - startTime} milliseconds`)
    }
    ```
  2. 后端计算时间：
    主要记录路由函数每个过程函数耗时，利用time包,记录渲染开始和结束时间，计算差值并找出**瓶颈**
    详细见time_measure.py文件
    设计如下回调函数
    ```python
    def measure_performance(func, *args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        duration = end_time - start_time
        print(f"Function {func.__name__} took {duration:.2f} seconds to execute.")
        return result
    ```
  3. 请求时间：
    Postman工具会显示请求的总时间
    目前技术不涉及优化这部分

# 1. ParallelView视图优化

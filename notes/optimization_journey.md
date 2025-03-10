> 学习过程仅为探索过程，理论权威性也需要建立在具体测试之上，各位请多指教

# 0. 性能记录方法（粗略）

  1. 前端渲染时间：

主要记录渲染函数耗时，利用`performance.now()`记录渲染开始和结束时间，计算差值
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

主要记录路由函数每个过程函数耗时，利用`time`包,记录渲染开始和结束时间，计算差值并找出**瓶颈**
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

## 1.1 前端优化

将前端接受到的数据分块，每块数据单独渲染，最后合并，减少渲染时间

## 1.2 后端优化

对应路由：`@api_bp.route('/api/cluster', methods=['get'])`



待优化函数：
`calculate_features`
`calc_final_scores`
`cluster_analysis`



参见：**test/ParallelView.py**文件

> **Q1:**
> `df = 1 / df.transform(lambda x: (x + 1))`
> `df= df.transform(lambda x: 1 / (x + 1))`
> 这两行代码哪一句效率更高？



> **Q2:**
> 该路由瓶颈在哪里？

> **A2:**
> 对于参数 num_students=1000, num_knowledges=50 的一次记录：
> Function generate_parallel_data took 0.72 seconds to execute.
> Function calculate_features took 9.01 seconds to execute.
> Function calc_final_scores took 0.03 seconds to execute.
> Function cluster_analysis took 0.34 seconds to execute.
> 多次执行明显得到瓶颈函数为calculate_features

> **OP2:**
> 分块计算 (parallel_calculate_features):
>
> - 数据被分割成多个小块 (chunks)。
>
> - 每个小块由 ProcessPoolExecutor 并行处理。
>
> - 最终结果通过 pd.concat(results) 合并。
>
> 并行化处理 (calculate_features_chunk):
>
> - 每个小块的数据单独进行 calculate_features 的计算。
>
> 某次运行结果：
>
> Function generate_parallel_data took 0.71 seconds to execute.
> Function parallel_calculate_features took **4.00** seconds to execute.
> Function calc_final_scores took 0.03 seconds to execute.
> Function cluster_analysis took 0.41 seconds to execute.


# 2. StudentView视图优化

## 2.1 前端优化

滚动按需加载可见的条目

1. **引入虚拟滚动**:
   - 使用 `@scroll="handleScroll"` 监听滚动事件。
   - 在 `handleScroll` 方法中计算当前可见的学生索引，并调用 `loadStudentPanel` 方法加载这些索引对应的学生面板。
2. **按需加载学生面板**:
   - 引入 `visibleIndices` 集合，用于记录哪些学生面板已经被加载。
   - `loadStudentPanel` 方法负责渲染单个学生面板。
   - `loadInitialBatch` 方法在初始化时加载前几个学生面板。
3. **更新 `renderEveryStudents` 方法**:
   - 移除原有的 `renderEveryStudents` 方法，因为现在我们按需加载学生面板。
4. **处理过滤变化**:
   - 在 `watch` 中监听 `getHadFilter` 变化，清空 `visibleIndices` 并重新加载初始批次的数据。
5. **更新限制**:
   - 在 `updateLimit` 方法中，清空 `visibleIndices` 并重新加载初始批次的数据。


## 2.2 后端优化
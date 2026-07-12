---
doc_type: question
chunk_strategy: none
title_ID: Question_5fgqjSBwTPG7KUV3it6O
score: 3
knowledge: g7R2j
sub_knowledge: g7R2j_e0v1yls8
question_type: programming
generated_at: "2026-07-12"
source: llm_assisted
---

# 二分查找

## 题干

给定一个按升序排列的整数数组 `nums` 和一个目标值 `target`，在数组中找到 `target` 并返回其下标。若不存在，返回 `-1`。

你可以假设数组中无重复元素。

## 要求

1. 时间复杂度 O(log n)。
2. 不得直接调用语言内置的二分查找函数。
3. 需正确处理空数组、单元素数组、目标在首尾位置、目标不存在等边界情况。

## 示例

**输入**

```text
nums = [1, 3, 5, 7, 9, 11]
target = 7
```

**输出**

```text
3
```

**输入**

```text
nums = [1, 3, 5, 7, 9, 11]
target = 2
```

**输出**

```text
-1
```

## 参考答案

```python
def search(nums, target):
    left, right = 0, len(nums) - 1
    while left <= right:
        mid = left + (right - left) // 2
        if nums[mid] == target:
            return mid
        if nums[mid] < target:
            left = mid + 1
        else:
            right = mid - 1
    return -1
```

## 解析

维护搜索区间 `[left, right]`，每次取中点 `mid` 与 `target` 比较并收缩区间。

- 循环条件使用 `left <= right`，保证区间为空时结束。
- 中点计算使用 `left + (right - left) // 2`，避免 `(left + right) // 2` 在部分语言中溢出。
- 当 `nums[mid] < target` 时令 `left = mid + 1`；否则令 `right = mid - 1`，避免死循环。

常见错误包括：循环条件写成 `left < right` 导致漏判、边界更新 off-by-one、未处理空数组直接访问 `nums[0]`。

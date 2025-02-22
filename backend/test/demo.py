import pandas as pd

# 示例数据
data = {
    'student_id': [1, 1, 1, 1, 2, 2, 2, 2],
    'question_id': ['q1', 'q1', 'q1', 'q2', 'q1', 'q1', 'q2', 'q2'],
    'state': ['错误1', '完全正确', '错误2', '部分正确', '错误1', '完全正确', '完全正确', '部分正确'],
    'timestamp': [1, 2, 3, 4, 5, 6, 7, 8]  # 假设有一个时间戳字段
}

df = pd.DataFrame(data)
print(df)
# 确保按 student_id 和 question_id 分组，并按时间排序
df = df.sort_values(by=['student_id', 'question_id', 'timestamp']).reset_index(drop=True)

# 计算 enthusiasm_bonus
def calculate_enthusiasm_bonus(group):
    correct_time = None  # 记录第一次完全正确的时间
    exploration_count = 0  # 探索次数
    
    for _, row in group.iterrows():
        if row['state'] == '完全正确' and correct_time is None:
            correct_time = row['timestamp']  # 第一次完全正确的时间
        elif correct_time is not None and row['timestamp'] > correct_time:
            # 如果在完全正确之后还有提交，视为探索行为
            exploration_count += 1
    
    return exploration_count

# 按 student_id 和 question_id 分组，计算每道题的探索次数
exploration_counts = (
    df.groupby(['student_id', 'question_id'])
      .apply(calculate_enthusiasm_bonus)
      .reset_index(name='exploration_count')
)

print(exploration_counts)

# 汇总每个学生的探索次数
enthusiasm_bonus = (
    exploration_counts.groupby(['student_id'])['exploration_count']
                      .sum()
                      .reset_index(name='enthusiasm_bonus')
)

print(enthusiasm_bonus)
import pandas as pd
import numpy as np
import time
from time_measure import *
import sys
import os
current_dir = os.path.dirname(os.path.abspath(__file__)) # 获取当前文件的目录
backend_dir = os.path.dirname(current_dir)      # 获取 backend 目录的路径
sys.path.append(backend_dir)                      # 将 tools 目录添加到 sys.path
from tools.ParallelView import *
from tools.fs import *

"""
df = 1 / df.transform(lambda x: (x + 1))
df = df.transform(lambda x: 1 / (x + 1))
这两行代码哪一句效率更高？
"""
def test_calc_matrix():
    # 创建一个示例 DataFrame
    np.random.seed(42)
    # 测试数据规模
    n = 1000
    df = pd.DataFrame({
        'student_ID': np.random.randint(1, 100, n),
        'knowledge': np.random.choice(['math', 'physics', 'chemistry'], n),
        'timeconsume': np.random.uniform(1, 100, n)
    })

    # 测试第一行代码
    start_time = time.time()
    df['tc_bonus_1'] = 1 / df.groupby(['student_ID', 'knowledge'])['timeconsume'].transform(lambda x: (x + 1))
    print(f"第一行代码耗时: {time.time() - start_time:.4f} 秒")

    # 测试第二行代码
    start_time = time.time()
    df['tc_bonus_2'] = df.groupby(['student_ID', 'knowledge'])['timeconsume'].transform(lambda x: 1 / (x + 1))
    print(f"第二行代码耗时: {time.time() - start_time:.4f} 秒")

    # 检查结果是否一致
    print("结果是否一致:", np.allclose(df['tc_bonus_1'], df['tc_bonus_2']))


"""
观察耗时最长的函数，寻找瓶颈
"""
def test_parallel_view(num_students=1000, num_titles=45, num_knowledges=8):
    submit_record_df, _, title_info_df = generate_parallel_view_data(num_students=1000, num_titles=45, num_knowledges=8)  # 使用模拟数据
    all_submit_records = process_non_numeric_values(merge_data(submit_record_df, title_info_df))
    features_df = measure_performance(calculate_features, all_submit_records)
    features_df = measure_performance(parallel_calculate_features, all_submit_records)
    final_scores = measure_performance(calc_final_scores, features_df, ['student_ID', 'knowledge'])
    target_data = final_scores.to_dict(orient='index')
    result = measure_performance(cluster_analysis, target_data, stu=None, every=True)
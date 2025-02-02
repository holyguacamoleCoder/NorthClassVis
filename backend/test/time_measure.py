import time
from mock_data import *
import sys
import os

# 获取当前文件的目录
current_dir = os.path.dirname(os.path.abspath(__file__))
# 获取 utils 目录的路径
utils_dir = os.path.join(current_dir, '..', 'utils')
# 将 utils 目录添加到 sys.path
sys.path.append(utils_dir)
from utils import *


def measure_performance(func, *args, **kwargs):
    start_time = time.time()
    result = func(*args, **kwargs)
    end_time = time.time()
    duration = end_time - start_time
    print(f"Function {func.__name__} took {duration:.2f} seconds to execute.")
    return result

def main():
    all_submit_records = measure_performance(generate_mock_data, num_students=10000, num_knowledges=10)
    # features_df = measure_performance(calculate_features, all_submit_records)
    features_df = measure_performance(parallel_calculate_features, all_submit_records)
    final_scores = measure_performance(calc_final_scores, features_df, ['student_ID', 'knowledge'])
    target_data = final_scores.to_dict(orient='index')
    result = measure_performance(cluster_analysis, target_data, stu=None, every=True)

if __name__ == "__main__":
    main()
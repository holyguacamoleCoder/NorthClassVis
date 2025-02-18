import pandas as pd
import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import MinMaxScaler
from concurrent.futures import ProcessPoolExecutor
import math

# --------------平行线图视图部分------------
#计算各个特征字段
def calculate_features(df):
    # print('calculate_features')
    # 计算答题得分加成
    df['score_bonus'] = df['score']

    # 提取 groupby 对象
    grouped = df.groupby(['student_ID', 'knowledge'])

    # 时间复杂度加成（假设timeconsume越小越好）
    df['tc_bonus'] = 1 / (grouped['timeconsume'].transform('mean') + 1)

    # 空间复杂度加成（假设memory越小越好）
    df['mem_bonus'] = 1 / (grouped['memory'].transform('mean') + 1)

    # 错误类型扣减（假设完全正确得分为1，否则为0）
    correct_state = 'Absolutely_Correct'
    df['error_type_penalty'] = df['state'].eq(correct_state).astype(int)

    # 尝试次数扣减（尝试次数越少越好）
    df['test_num_penalty'] = grouped['title_ID'].cumcount() + 1

    # 排名加成（根据最终得分和提交次序）
    df['rank_bonus'] = df.groupby(['student_ID', 'knowledge', 'title_ID'])['time'].rank(method='dense', ascending=True)

    return df
# def calculate_features(df):
#     # 计算答题得分加成
#     df['score_bonus'] = df['score']
#     # 时间复杂度加成（假设timeconsume越小越好）
#     df['tc_bonus'] = 1 / df.groupby(['student_ID', 'knowledge'])['timeconsume'].transform(lambda x: (x + 1))

#     # 空间复杂度加成（假设memory越小越好）
#     df['mem_bonus'] = 1 / df.groupby(['student_ID', 'knowledge'])['memory'].transform(lambda x: (x + 1))

#     # 错误类型扣减（假设完全正确得分为1，否则为0）
#     correct_state = 'Absolutely_Correct'  # 假设完全正确的状态名称为“完全正确”
#     df['error_type_penalty'] = df['state'].apply(lambda x: 1 if x == correct_state else 0)

#     # 尝试次数扣减（尝试次数越少越好）
#     df['test_num_penalty'] = df.groupby(['student_ID', 'knowledge'])['title_ID'].cumcount() + 1

#     # 排名加成（根据最终得分和提交次序）
#     df['rank_bonus'] = df.groupby(['student_ID', 'knowledge', 'title_ID'])['time'].rank(method='dense', ascending=True)

#     return df



def parallel_calculate_features(df, num_workers=1):
    chunk_size = math.ceil(len(df) / num_workers)
    chunks = [df.iloc[i:i + chunk_size] for i in range(0, len(df), chunk_size)]

    with ProcessPoolExecutor(max_workers=num_workers) as executor:
        results = list(executor.map(calculate_features, chunks))
    
    return pd.concat(results).sort_index()

# 计算每个学生各个知识点总分
def calc_final_scores(after_features_df, groupApply):
    # 按学生ID和知识点分组，并计算每个学生的总分
    grouped = after_features_df.groupby(groupApply).agg({
        'score_bonus': 'sum',
        'tc_bonus': 'sum',
        'mem_bonus': 'sum',
        'error_type_penalty': 'mean',
        'test_num_penalty': 'min',  # 取最少尝试次数
        'rank_bonus': 'sum'
    })
    grouped['MS'] = grouped.sum(axis=1)  # 计算总分

    # 将多层索引转换为单层索引，并添加知识点列
    grouped.reset_index(inplace=True)

    # 汇总每个学生在所有知识点上的分数
    index = groupApply[0] # 'student_ID'
    columns = groupApply[1:] #'knowledge' 或者 ['week','knowledge']
    final_scores = grouped.pivot_table(index=index, columns=columns, values='MS')
    # 如果某些学生没有做某些知识点的题目，那么在该知识点上分数为0
    final_scores.fillna(0, inplace=True)

    # 对数变换
    log_transformed_scores = np.log1p(final_scores)

    # 分位数归一化
    quantile_scaler = MinMaxScaler()
    quantile_normalized_scores = pd.DataFrame(quantile_scaler.fit_transform(log_transformed_scores),
                                              index=log_transformed_scores.index,
                                              columns=log_transformed_scores.columns)

    return quantile_normalized_scores

# 聚类分析
def cluster_analysis(students_data, stu=None, every=None):
   # 提取特征向量
    features = []
    for student_id, values in students_data.items():
        if isinstance(values, dict):
            feature_vector = list(values.values())
            features.append(feature_vector)
        else:
            raise ValueError(f"Invalid data format for student {student_id}: {values}")
   
    features_array = np.array(features)

    # 设定聚类的数量，这里假设为3个聚类
    n_clusters = 3

    # 创建KMeans实例
    kmeans = KMeans(n_clusters=n_clusters, max_iter=100, random_state=42)

    # 训练模型
    kmeans.fit(features_array)

    # 获取聚类中心
    cluster_centers = kmeans.cluster_centers_

    # 输出聚类中心
    # print("Cluster Centers:")
    # print(cluster_centers)

    if every is not None:
    # 输出每个学生的聚类分配
        predictions = kmeans.predict(features_array)
        result = {}
        for student_id, prediction in zip(students_data.keys(), predictions):
            # print(f"Student ID: {student_id}, Assigned to Cluster: {prediction}")
            result[student_id] = {
                "knowledge":students_data[student_id],
                "cluster": int(prediction)
            }
        # print(result)
        return result

    if stu is not None:
        # 获取每个聚类中心的学生对象
        cluster_centers = kmeans.cluster_centers_
        cluster_center_students = []

        students_data_df = pd.DataFrame(students_data).T

        for center in cluster_centers:
            # 找到距离每个聚类中心最近的学生
            closest_student = students_data_df.apply(lambda row: np.linalg.norm(row - center), axis=1).idxmin()
            cluster_center_students.append(closest_student)

        return cluster_center_students
    
    result = {}
   
    for i, center in enumerate(cluster_centers):
        result[str(i)] = {
            "cluster": i,
            # """
            #  next(iter(students_data)) 获取 students_data 字典中的第一个学生的 ID。
            #  students_data[next(iter(students_data))] 获取该学生的知识点分数字典。
            #  .keys() 返回该学生的所有知识点名称。
            #  zip(students_data[next(iter(students_data))].keys(), center) 将知识点名称与聚类中心的特征向量元素配对。
            #  dict(...) 将这些配对转换为字典，其中键是知识点名称，值是聚类中心在该知识点上的分数。
            # """
            "knowledge": dict(zip(students_data[next(iter(students_data))].keys(), center))
        }
    return result
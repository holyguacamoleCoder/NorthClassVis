import pandas as pd
import os
import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import MinMaxScaler

# 获取当前目录
current_dir = os.path.dirname(os.path.abspath(__file__))
# 获取数据目录
data_dir = os.path.join(current_dir, '../data/')

# 获取数据文件
class_dir = os.path.join(data_dir, 'Data_SubmitRecord/')
classFilename = os.path.join(class_dir, 'SubmitRecord-Class1.csv') # 提交记录表格
titleFilename = os.path.join(data_dir, 'Data_TitleInfo.csv')       # 题目信息表格
studentFilename = os.path.join(data_dir, 'Data_StudentInfo.csv')   # 学生信息表格

# 加载数据
def load_data(filename):
    try:
        df = pd.read_csv(filename)
        return df
    except Exception as e:
        print(f"Error loading data: {e}")
        return None

# 拼接文件为新df
def contact_data(classList):
    return pd.concat([load_data(os.path.join(data_dir,'SubmitRecord-' + class_i['text'] + '.csv')) for class_i in classList if class_i['checked']], axis=0)

# 合并数据题目和提交记录
# filename2: 题目信息文件
def merge_data(f1, f2):
    if isinstance(f1, str):
        f1 = load_data(f1) 
    if isinstance(f2, str):
        f2 = load_data(f2) 
    merged_data = pd.merge(f1, f2[['title_ID', 'knowledge']], on='title_ID', how='left')
    return merged_data

# ------------学生视图部分----------------

# 将数据转换为树状图数据结构
def transform_data(df):
    # # 分组并聚合数据
    # grouped = df.groupby(['student_ID', 'title_ID', 'state'])['score'].sum().reset_index()
    # grouped_u = df.groupby(['student_ID', 'title_ID', 'state'])['score'].count().reset_index()
    # grouped['times'] = grouped_u['score']
    
    # 构建树状图数据结构
    root = {'name': 'Root', 'children': []}
    # print('df[student_ID]',df['student_ID'])
    students = df['student_ID'].unique()
    print(students[0])
    for student in students:
        student_data = df[df['student_ID'] == student]
        
        student_node = {'name': str(student), 'children': []}
        
        titles = student_data['title_ID'].unique()
        
        for title in titles:
            title_data = student_data[student_data['title_ID'] == title]
            
            title_node = {'name': str(title), 'children': []}
            
            states = title_data['state'].unique()
            # if(title == 'Question_3MwAFlmNO8EKrpY5zjUd' and student == '01d8aa21ef476b66c573'):
            #     print(title_data)
            #     print(states)
            for state in states:
                state_data = title_data[title_data['state'] == state]
                state_node = {
                        'name': state,
                        'times': len(state_data),
                        'value': int(state_data['score'].max()),
                        }
                
                title_node['children'].append(state_node)
            
            if len(title_node['children']) > 0:
                student_node['children'].append(title_node)
        
        if len(student_node['children']) > 0:
            root['children'].append(student_node)
    
    return root

# -------------问题视图部分------------------------

# 题目-时间轴数据处理
def process_timeline_data(merged_data, title_id):
    timeline_data = merged_data[merged_data['title_ID'] == title_id].copy()
    timeline_data['time'] = pd.to_datetime(timeline_data['time'], unit='s')
    timeline_data['date'] = timeline_data['time'].dt.date
    timeline_data = timeline_data.groupby(['date']).agg({
        'score': ['mean', 'count'],
    }).reset_index()
    timeline_data.columns = ['date', 'average_score', 'submission_count']
    timeline_data['date'] = timeline_data['date'].astype(str)
    return timeline_data.to_dict(orient='records')

# 总分分布数据处理
def process_distribution_data(merged_data, title_id):
    distribution_data = merged_data[merged_data['title_ID'] == title_id].copy()
    distribution_data = distribution_data.groupby('score').size().reset_index(name='count')
    total_submissions = distribution_data['count'].sum()
    distribution_data['percentage'] = distribution_data['count'] / total_submissions * 100
    return distribution_data.to_dict(orient='records')


# 获取特定知识点下的所有题目数据
def get_titles_data_by_knowledge(merged_data, knowledge, limit=None):
    # 获取特定知识点下的所有题目
    titles = merged_data[merged_data['knowledge'] == knowledge][['title_ID', 'knowledge']].drop_duplicates()
    
    # 如果有限制数量，则只取前limit个题目
    if limit is not None:
        titles = titles.head(limit)
    
    # 对每个题目提取所需的数据
    titles_data = []
    for _, row in titles.iterrows():
        title_id = row['title_ID']
        timeline_data = process_timeline_data(merged_data, title_id)
        distribution_data = process_distribution_data(merged_data, title_id)
        
        # 合并时间轴数据和分布数据
        title_data = {
            'title_id': title_id,
            'knowledge': row['knowledge'],
            'timeline': timeline_data,
            'distribution': distribution_data
        }
        titles_data.append(title_data)
    
    return titles_data


# --------------三散点图视图部分------------
# 处理非数字值
def process_non_numeric_values(df):
    # 将非数字值转换为NaN
    df['timeconsume'] = pd.to_numeric(df['timeconsume'], errors='coerce')
    df['memory'] = pd.to_numeric(df['memory'], errors='coerce')
    
    # 使用组内平均值填充NaN
    df['timeconsume'] = df.groupby(['student_ID', 'knowledge'])['timeconsume'].transform(lambda x: x.fillna(x.mean()))
    df['memory'] = df.groupby(['student_ID', 'knowledge'])['memory'].transform(lambda x: x.fillna(x.mean()))

    return df


# 计算各个特征字段
def calculate_features(df):
    # 计算答题得分加成
    df['score_bonus'] = df['score']
    # grouped = df.groupby(['student_ID', 'knowledge'])
    # 时间复杂度加成（假设timeconsume越小越好）
    df['tc_bonus'] = df.groupby(['student_ID', 'knowledge'])['timeconsume'].transform(lambda x: 1 / (x + 1))

    # 空间复杂度加成（假设memory越小越好）
    df['mem_bonus'] = df.groupby(['student_ID', 'knowledge'])['memory'].transform(lambda x: 1 / (x + 1))

    # 错误类型扣减（假设完全正确得分为1，否则为0）
    correct_state = 'Absolutely_Correct'  # 假设完全正确的状态名称为“完全正确”
    df['error_type_penalty'] = df['state'].apply(lambda x: 1 if x == correct_state else 0)

    # 尝试次数扣减（尝试次数越少越好）
    df['test_num_penalty'] = df.groupby(['student_ID', 'knowledge'])['title_ID'].cumcount() + 1

    # 排名加成（根据最终得分和提交次序）
    df['rank_bonus'] = df.groupby(['student_ID', 'knowledge', 'title_ID'])['time'].rank(method='dense', ascending=True)

    return df

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
    # print(grouped)
    # 将多层索引转换为单层索引，并添加知识点列
    grouped.reset_index(inplace=True)

    # 汇总每个学生在所有知识点上的分数
    index = groupApply[0] # 'student_ID'
    columns = groupApply[1:] #'knowledge' 或者 ['week','knowledge']
    final_scores = grouped.pivot_table(index=index, columns=columns, values='MS')
    # 如果某些学生没有做某些知识点的题目，那么在该知识点上分数为0
    final_scores.fillna(0, inplace=True)
    # print("final_scores:")
    # print(final_scores)

    # 对数变换
    log_transformed_scores = np.log1p(final_scores)

    # 分位数归一化
    quantile_scaler = MinMaxScaler()
    quantile_normalized_scores = pd.DataFrame(quantile_scaler.fit_transform(log_transformed_scores),
                                              index=log_transformed_scores.index,
                                              columns=log_transformed_scores.columns)

    # 按知识点进行局部归一化
    normalized_scores = final_scores.copy()
    for col in final_scores.columns:
        scaler = MinMaxScaler()
        normalized_scores[col] = scaler.fit_transform(final_scores[[col]])

    # result = {
    #     "log_quantile": quantile_normalized_scores.to_dict(orient='index'),
    #     "local_normlized": normalized_scores.to_dict(orient='index')
    # }
    result =  quantile_normalized_scores
    # result =  normalized_scores.to_dict(orient='index')
    return result

# 聚类分析
def cluster_analysis(students_data, stu=None, every=None):
   # 提取特征向量   # 提取特征向量
    features = []
    for student_id, values in students_data.items():
        features.append(list(values.values()))

    features_array = np.array(features)

    # 设定聚类的数量，这里假设为3个聚类
    n_clusters = 3

    # 创建KMeans实例
    kmeans = KMeans(n_clusters=n_clusters)

    # 训练模型
    kmeans.fit(features_array)

    # 获取聚类中心
    cluster_centers = kmeans.cluster_centers_
    cluster_centers_info = []
    for i, center in enumerate(cluster_centers):
        cluster_centers_info.append({
            "cluster": i,
            "center": center
        })
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

        students_data = pd.DataFrame(students_data).T

        for center in cluster_centers:
            # 找到距离每个聚类中心最近的学生
            closest_student = students_data.apply(lambda row: np.linalg.norm(row - center), axis=1).idxmin()
            cluster_center_students.append(closest_student)

        return cluster_center_students
    
    result = {}
    for i in range(len(cluster_centers)):
        center_score = cluster_centers_info[i]['center']
        center_cluster = cluster_centers_info[i]['cluster']
        result[str(i)] = {
        "cluster": center_cluster,
        "knowledge":{
        "b3C9s": center_score[0],
        "g7R2j": center_score[1],
        "k4W1c": center_score[2],
        "m3D1v": center_score[3],
        "r8S3g": center_score[4],
        "s8Y2f": center_score[5],
        "t5V9e": center_score[6],
        "y9W5d": center_score[7],
        }
        }
    return result


# -------------周视图部分--------------
def calculate_week_of_year(timestamp, start_date=None):
    """
    根据给定的时间戳计算其属于哪一周。
    
    参数:
    - timestamp (int): 时间戳，单位秒。
    - start_date (datetime.datetime): 可选参数，指定起始周的第一天。如果没有提供，
      则使用数据集中最早的日期作为起始周的第一天。
    
    返回:
    - int: 对应的时间戳所在的周数。
    """
    timestamp = pd.to_datetime(timestamp, unit='s')
    start_timestamp = pd.to_datetime(start_date, unit='s') if start_date else None
    # if start_date is None:
    #     # 如果没有提供起始日期，则查找数据集中最早的日期作为起始日期
    #     min_date = pd.to_datetime(df['timestamp']).min()
    #     start_date = min_date.floor('D')  # 地板化到天
    # else:
    #     start_date = pd.to_datetime(start_date)
    
    delta = (timestamp - start_timestamp).days // 7
    return delta


def transform_data_for_visualization(data):
    """
    将提供的数据转换为适合前端可视化的格式。
    
    参数:
    - data (dict): 包含学生ID及其知识点分数的数据字典。
    - e.g. data = {
    '01d8aa21ef476b66c573': {(36, 'r8S3g'): 0.0, (36, 't5V9e'): 0.0, ...},
    '03aa0b20dd4af1888eef': {(36, 'r8S3g'): 0.0, (36, 't5V9e'): 0.0, ...},
    ...
}
    
    返回:
    - dict: 转换后的数据字典，适合JSON序列化。
    - e.g.
    {
    "students": [
        {
            "id": "01d8aa21ef476b66c573",
            "weeks": [
                {
                    "week": 36,
                    "scores": {
                        "r8S3g": 0.0,
                        "t5V9e": 0.0,
                        ...
                    }
                },
                ...
            ]
        },
        ...
    ]
}
    """
    students = []
    
    for student_id, weekly_scores in data.items():
        weeks = []
        
        # 遍历每个学生的所有周数据
        for week_number in range(min([w for w, _ in weekly_scores.keys()]), max([w for w, _ in weekly_scores.keys()]) + 1):
            scores = {kp: weekly_scores.get((week_number, kp), 0.0) for kp in set(kp for _, kp in weekly_scores.keys())}
            
            weeks.append({
                "week": week_number,
                "scores": scores
            })
        
        students.append({
            "id": student_id,
            "weeks": weeks
        })
    
    return {"students": students}
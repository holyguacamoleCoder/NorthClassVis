import pandas as pd

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
# def get_titles_data_by_knowledge(merged_data, knowledge, limit=None):
def get_all_titles_data(merged_data, limit=None):
    # 获取特定知识点下的所有题目
    # titles = merged_data[merged_data['knowledge'] == knowledge][['title_ID', 'knowledge']].drop_duplicates()
    titles = merged_data[['title_ID', 'knowledge']].drop_duplicates()
    
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
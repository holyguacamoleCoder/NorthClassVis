import pandas as pd
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
    
    # 获取
    return {"students": students}


def calculate_peak_data(df, day):
    """
    接收原始数据，返回按学生、周、半周分类的提交数量统计
    :param df: pd.DataFrame 原始数据，必须包含 'student_ID', 'time'
    :param day: int (1~7)，指定划分前半周/后半周的临界星期
    :return: dict 格式 {student_id: {week: {'Mon_to_Day': cnt, 'after_Day_to_Sun': cnt}}}
    """
    df = df.copy()
    df['time'] = pd.to_datetime(df['time'], unit='s')
    start_date = df['time'].min()

    # 计算周数
    df['week'] = df['time'].apply(lambda x: calculate_week_of_year(x, start_date=start_date))

    # 判断时间段
    df['weekday'] = df['time'].dt.weekday
    df['period'] = df['weekday'].apply(lambda x: 'Mon_to_Day' if x <= day else 'after_Day_to_Sun')

    # 按照 student_ID + week + period 分组统计
    grouped = df.groupby(['student_ID', 'week', 'period']).size().reset_index(name='count')
    # pivot 表格，将 period 转换为列
    pivoted = grouped.pivot_table(
        index=['student_ID', 'week'],
        columns='period',
        values='count',
        fill_value=0,
        aggfunc='sum'
    ).reindex(columns=['Mon_to_Day', 'after_Day_to_Sun'], fill_value=0)
    
    # 格式转换成想要的结构
     # ✅ 新增：格式转换成你想要的结构
    result_list = []
    for student_id, group in pivoted.groupby(level='student_ID'):
        weeks = []
        for week_num in group.index.get_level_values('week').unique():
            row = group.xs(week_num, level='week')
            weeks.append({
                "week": week_num,
                "Mon_to_Day": int(row['Mon_to_Day'].iloc[0]),
                "after_Day_to_Sun": int(row['after_Day_to_Sun'].iloc[0])
            })
        result_list.append({
            "id": student_id,
            "weeks": weeks
        })
    return {"peaks": result_list}
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
    
    return {"students": students}
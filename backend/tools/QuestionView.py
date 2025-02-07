import pandas as pd
# -------------问题视图部分------------------------

# 题目-时间轴数据处理
def process_timeline_data(merged_data, title_id):
    timeline_data = merged_data[merged_data['title_ID'] == title_id].copy()
    timeline_data['time'] = pd.to_datetime(timeline_data['time'], unit='s')
    timeline_data['date'] = timeline_data['time'].dt.date
    timeline_data = timeline_data.groupby(['date']).agg({
        'score': 'count',
    }).reset_index()
    timeline_data.columns = ['date', 'submission_count']
    timeline_data['date'] = timeline_data['date'].astype(str)
    return timeline_data.to_dict(orient='records')

# 总分分布数据处理
def process_distribution_data(merged_data, title_id):
    distribution_data = merged_data[merged_data['title_ID'] == title_id].copy()
    distribution_data = distribution_data.groupby('score').size().reset_index(name='count')
    total_submissions = distribution_data['count'].sum()
    distribution_data['percentage'] = distribution_data['count'] / total_submissions * 100
    return distribution_data.to_dict(orient='records')

# 获取平均分数
def get_avg_score(merged_data, title_id):
    avg_score = merged_data[merged_data['title_ID'] == title_id]['score'].mean()
    return float(avg_score)

# 获取提交总数
def get_sum_submit(merged_data, title_id):
    sum_submit = merged_data[merged_data['title_ID'] == title_id]['title_ID'].count()
    return float(sum_submit)

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
        avg_score = get_avg_score(merged_data, title_id)
        sum_submit =  get_sum_submit(merged_data, title_id)        
        # 合并时间轴数据和分布数据
        title_data = {
            'title_id': title_id,
            'knowledge': row['knowledge'],
            'timeline': timeline_data,
            'distribution': distribution_data,
            'avg_score': avg_score,
            'sum_submit': sum_submit
        }
        titles_data.append(title_data)
    
    return titles_data


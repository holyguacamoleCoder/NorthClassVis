# ------------学生视图部分----------------
# 将数据转换为树状图数据结构
def transform_data(df, student_info):
    # 构建树状图数据结构
    root = {'name': 'Root', 'children': []}
    students = df['student_ID'].unique()

    for student in students:
        student_data = df[df['student_ID'] == student]
        # 获取major信息
        major = student_info[student_info['student_ID'] == student]['major'].iloc[0]
        
        student_node = {
            'name': str(student),
            'class': student_data['class'].iloc[0],
            'major': major,
            'children': []
        }
        
        titles = student_data['title_ID'].unique()
        
        for title in titles:
            title_data = student_data[student_data['title_ID'] == title]
            
            title_node = {'name': str(title), 'children': []}
            
            states = title_data['state'].unique()
            
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
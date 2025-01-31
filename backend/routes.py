from flask import Blueprint, request, jsonify
import utils as us
# ----- 总配置部分--------
config = {
    # 创建蓝图对象
    'api_bp' : Blueprint('api', __name__),
    # 配置总处理文件类型
    'all_class_df': us.load_data(us.classFilename),
    "classList": []
}
# ---- 初始化 --------- 
api_bp = config['api_bp']
for i in range(1, 16):
    config['classList'].append({"checked": False, "text": f"Class{i}", 'id': i})
config['classList'][0]['checked'] = True
@api_bp.route('/api/filter', methods=['GET'])
def filter_info():
    return jsonify(config['classList'])

# ----------筛选班级部分------------
@api_bp.route('/api/filter_classes', methods=['POST'])
def merge_classes():
    # 获取前端发送的数据，这里假设前端发送的是JSON格式的数据
    data = request.get_json()
    
    # 检查是否接收到有效的数据
    if not data or 'classes' not in data:
        return jsonify({'error': 'No classes provided'}), 400
    
    # 获取班级列表
    classes = data['classes']
    # print(classes)
    # 检查班级列表中的每个班级是否存在
    for class_i in classes:
        # print('class_i', class_i)
        if class_i['id'] > 15 or class_i['id'] < 1:
            return jsonify({'error': f'Class {class_i['id']} does not exist'}), 400
    
    # 获取对应的DataFrame并合并
    contact_df = us.contact_data(classes)
    
    # 将合并后的DataFrame转换为JSON格式
    config['all_class_df'] = contact_df
    config['classList'] = classes

    # 返回处理后的结果
    response = {
        'data': classes,
        'message': 'Classes have been successfully merged.'
    }
    
    return jsonify(response)


# ------------学生视图部分-----------
@api_bp.route('/api/submissions', methods=['GET'])
def get_submissions():
    df = config['all_class_df']
    if df is None:
        return jsonify({"error": "Failed to load submissions data."}), 500

    # 获取查询参数
    student_id = request.args.get('studentID')
    title_id = request.args.get('titleID')
    limit = request.args.get('limit')

    # 过滤数据
    filtered_records = df.copy()
    if student_id:
        try:
            student_id = int(student_id)
            filtered_records = filtered_records[filtered_records['student_ID'] == student_id]
        except ValueError:
            return jsonify({"error": "Invalid studentID parameter."}), 400
    if title_id:
        try:
            title_id = int(title_id)
            filtered_records = filtered_records[filtered_records['title_ID'] == title_id]
        except ValueError:
            return jsonify({"error": "Invalid titleID parameter."}), 400

    # 如果指定了 limit 参数，则返回指定数量的记录
    if limit:
        try:
            limit = int(limit)
            filtered_records = filtered_records.head(limit)
        except ValueError:
            return jsonify({"error": "Invalid limit parameter."}), 400

    # 将DataFrame转换为字典列表
    records_list = filtered_records.to_dict(orient='records')

    # 返回JSON响应
    return jsonify(records_list)

@api_bp.route('/api/tree_data', methods=['GET'])
def get_tree_data():
    df = config['all_class_df']
    limit = request.args.get('limit')

    if df is None:
        return jsonify({'error': 'Failed to load data.'}), 500

    # 转换数据
    tree_data = us.transform_data(df)
    
    if limit:
        try:
            limit = int(limit)
            # 限制根节点下的子节点数量
            tree_data['children'] = tree_data['children'][:limit]
        except ValueError:
            return jsonify({"error": "Invalid limit parameter."}), 400


    return jsonify(tree_data)

# ----------------问题视图部分------------------
def merged_process_data():
    return us.process_non_numeric_values(us.merge_data(config['all_class_df'], us.titleFilename))
@api_bp.route('/api/timeline/<title_id>')
def get_timeline_data(title_id):
    timeline_data = us.process_timeline_data(merged_process_data(), title_id)
    return jsonify(timeline_data)

@api_bp.route('/api/distribution/<title_id>')
def get_distribution_data(title_id):
    distribution_data = us.process_distribution_data(merged_process_data(), title_id)
    return jsonify(distribution_data)

@api_bp.route('/api/questions', methods=['GET'])
def get_question():
    knowledge = request.args.get('knowledge', default=None, type=str)
    title_id = request.args.get('title_id', default=None, type=int)
    limit = request.args.get('limit', default=None, type=int)

    if title_id is not None:
        # 如果指定了题目ID，则返回单个题目的数据
        title_data = {
            'title_id': title_id,
            'knowledge': merged_process_data().loc[merged_process_data()['title_ID'] == title_id, 'knowledge'].iloc[0],
            'timeline': us.process_timeline_data(merged_process_data(), title_id),
            'distribution': us.process_distribution_data(merged_process_data(), title_id)
        }
        return jsonify([title_data])
    elif knowledge is not None:
        # 如果指定了知识点，则返回该知识点下所有题目的数据
        titles_data = us.get_titles_data_by_knowledge(merged_process_data(), knowledge, limit)
        return jsonify(titles_data)
    else:
        # 如果没有指定知识点或题目ID，则返回所有题目的数据
        unique_knowledges = merged_process_data()['knowledge'].unique()
        all_titles_data = {}
        for knowledge in unique_knowledges:
            all_titles_data[knowledge] = us.get_titles_data_by_knowledge(merged_process_data(), knowledge, limit)
        return jsonify(all_titles_data)
    

@api_bp.route('/api/calculate_scores', methods=['GET'])
def calculate_scores():
    # 计算所有学生的特征
    all_submit_records = us.calculate_features(merged_process_data())
    # print(all_submit_records['tc_bonus'])

    # 计算每个学生的总分
    final_scores = us.calc_final_scores(all_submit_records, ['student_ID', 'knowledge'])
    result = final_scores.to_dict(orient='index')
    
    return jsonify(result)

# ----------------聚类分析部分------------------
@api_bp.route('/api/cluster', methods=['get'])
def cluster_analysis():
    stu = request.args.get('stu')
    every = request.args.get('every')

    all_submit_records = us.calculate_features(merged_process_data())
    final_scores = us.calc_final_scores(all_submit_records, ['student_ID', 'knowledge'])
    target_data = final_scores.to_dict(orient='index')

    result = us.cluster_analysis(target_data, stu = stu, every = every)
    # print(result)
    return jsonify(result)



# ----------------周图部分------------------
@api_bp.route('/api/week', methods=['get'])
def week_analysis():
    df = merged_process_data()
    start_date = df['time'].min()
    # start_date = us.pd.to_datetime('2023-9-10')
    df['week'] = df['time'].apply(lambda x: us.calculate_week_of_year(x, start_date=start_date))
    all_submit_records = us.calculate_features(df)
    final_scores = us.calc_final_scores(all_submit_records, ['student_ID','week','knowledge'])
    result = final_scores.to_dict(orient='index')
    result = us.transform_data_for_visualization(result)
    # print(result)
    return jsonify(result)


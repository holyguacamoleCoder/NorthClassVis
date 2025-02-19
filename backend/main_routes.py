from flask import Blueprint, request, jsonify
from tools import fs as fs
from tools import ParallelView as pv
from tools import StudentView as sv
from tools import QuestionView as qv
from tools import WeekView as wv
from routes.cluster_routes import ClusterRoutes
from routes.student_routes import StudentRoutes

# ----- 总配置部分--------
# ----- 单例模式 ------
config = {
    # 创建蓝图对象
    'api_bp' : Blueprint('api', __name__),
    # 配置总处理文件类型
    'all_class_df': fs.load_data(fs.classFilename),
    "classList": []
}

# ---- 初始化 --------- 
api_bp = config['api_bp']
for i in range(1, 16):
    config['classList'].append({"checked": False, "text": f"Class{i}", 'id': i})
config['classList'][0]['checked'] = True


# ----------筛选视图部分------------
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
            return jsonify({"error": f"Class {class_i['id']} does not exist"}), 400
    
    # 获取对应的DataFrame并合并
    contact_df = fs.contact_data(classes)
    
    # 将合并后的DataFrame转换为JSON格式
    config['all_class_df'] = contact_df
    config['classList'] = classes

    # 返回处理后的结果
    response = {
        'data': classes,
        'message': 'Classes have been successfully merged.'
    }
    
    return jsonify(response)

# ----------------问题视图部分------------------
def merged_process_data():
    return fs.process_non_numeric_values(fs.merge_data(config['all_class_df'], fs.titleFilename))
@api_bp.route('/api/timeline/<title_id>')
def get_timeline_data(title_id):
    timeline_data = qv.process_timeline_data(merged_process_data(), title_id)
    return jsonify(timeline_data)

@api_bp.route('/api/distribution/<title_id>')
def get_distribution_data(title_id):
    distribution_data = qv.process_distribution_data(merged_process_data(), title_id)
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
            'timeline': qv.process_timeline_data(merged_process_data(), title_id),
            'distribution': qv.process_distribution_data(merged_process_data(), title_id)
        }
        return jsonify([title_data])
    elif knowledge is not None:
        # 如果指定了知识点，则返回该知识点下所有题目的数据
        titles_data = pv.get_titles_data_by_knowledge(merged_process_data(), knowledge, limit)
        return jsonify(titles_data)
    else:
        # # 如果没有指定知识点或题目ID，则返回所有题目的数据
        all_titles_data = qv.get_all_titles_data(merged_process_data(), limit)
        return jsonify(all_titles_data)
    
# ----------------画像视图部分 雷达图--------------------
@api_bp.route('/api/calculate_scores', methods=['GET'])
def calculate_scores():
    # 计算所有学生的特征
    all_submit_records = pv.calculate_features(merged_process_data())
    # print(all_submit_records['tc_bonus'])

    # 计算每个学生的总分，不区分知识点
    final_scores = pv.calc_final_scores(all_submit_records, ['student_ID'])
    result = final_scores.to_dict(orient='index')
    
    return jsonify(result)


# ----------------周图部分------------------
@api_bp.route('/api/week', methods=['get'])
def week_analysis():
    df = merged_process_data()
    start_date = df['time'].min()
    # start_date = us.pd.to_datetime('2023-9-10')
    df['week'] = df['time'].apply(lambda x: wv.calculate_week_of_year(x, start_date=start_date))
    all_submit_records = pv.calculate_features(df)
    final_scores = pv.calc_final_scores(all_submit_records, ['student_ID','week','knowledge'])
    result = final_scores.to_dict(orient='index')
    result = wv.transform_data_for_visualization(result)
    # print(result)
    return jsonify(result)

# 注册 student 蓝图
student_routes = StudentRoutes(config['all_class_df'])
api_bp.register_blueprint(student_routes.student_bp, url_prefix='/api')

# 注册 cluster 蓝图
cluster_routes = ClusterRoutes(merged_process_data)
api_bp.register_blueprint(cluster_routes.cluster_bp, url_prefix='/api')
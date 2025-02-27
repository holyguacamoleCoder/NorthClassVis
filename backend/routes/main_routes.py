from flask import request, jsonify
from tools import fileSystem as fs
from routes.config import Config
from routes.cluster_routes import ClusterRoutes
from routes.student_routes import StudentRoutes
from routes.question_routes import QuestionRoutes
from routes.week_routes import WeekRoutes

class ConfigRoutes:
    def __init__(self, config):
        self.config = config
        self.api_bp = config.api_bp

        # 注册路由
        self.api_bp.add_url_rule('/api/filter', view_func=self.filter_info, methods=['GET'])
        self.api_bp.add_url_rule('/api/filter_classes', view_func=self.merge_classes, methods=['POST'])

    def filter_info(self):
        return jsonify(self.config.classList)

    def merge_classes(self):
        # 获取前端发送的数据，这里假设前端发送的是JSON格式的数据
        data = request.get_json()

        # 检查是否接收到有效的数据
        if not data or 'classes' not in data:
            return jsonify({'error': 'No classes provided'}), 400

        # 获取班级列表
        classes = data['classes']

        # 检查班级列表中的每个班级是否存在
        for class_i in classes:
            if class_i['id'] > 15 or class_i['id'] < 1:
                return jsonify({"error": f"Class {class_i['id']} does not exist"}), 400

        # 获取对应的DataFrame并合并
        contact_df = fs.contact_data(classes)

        # 将合并后的DataFrame转换为JSON格式
        self.config.all_class_df = contact_df
        self.config.classList = classes
        self.config.merged_process_data = self.config.merge_process_data()

        # 更新所有相关类的 merged_process_data
        cluster_routes.update_merged_process_data(self.config.merged_process_data)
        student_routes.update_all_class_df(self.config.merged_process_data)
        question_routes.update_merged_process_data(self.config.all_class_df)
        week_routes.update_merged_process_data(self.config.merged_process_data)

        # 返回处理后的结果
        response = {
            'data': classes,
            'message': 'Classes have been successfully merged.'
        }

        return jsonify(response)


# 创建 Config 实例
config = Config()

# 创建 ConfigRoutes 实例
config_routes = ConfigRoutes(config)

# 注册 student 蓝图
student_routes = StudentRoutes(config.all_class_df)
config_routes.api_bp.register_blueprint(student_routes.student_bp, url_prefix='/api')

# 注册 cluster 蓝图
cluster_routes = ClusterRoutes(config.merged_process_data)
config_routes.api_bp.register_blueprint(cluster_routes.cluster_bp, url_prefix='/api')

# 注册 question 蓝图
question_routes = QuestionRoutes(config.merged_process_data)
config_routes.api_bp.register_blueprint(question_routes.question_bp, url_prefix='/api')

# 注册 week 蓝图
week_routes = WeekRoutes(config.merged_process_data)
config_routes.api_bp.register_blueprint(week_routes.week_bp, url_prefix='/api')

api_bp = config.api_bp

# ----- 总配置部分--------
# config = {
#     # 创建蓝图对象
#     'api_bp' : Blueprint('api', __name__),
#     # 配置总处理文件类型
#     'all_class_df': fs.load_data(fs.classFilename),
#     "classList": [],
#     "merged_process_data": None,
# }

# def merge_process_data():
#     return fs.process_non_numeric_values(fs.merge_data(config['all_class_df'], fs.titleFilename))


# # ---- 初始化 --------- 
# api_bp = config['api_bp']
# for i in range(1, 16):
#     config['classList'].append({"checked": False, "text": f"Class{i}", 'id': i})
# config['classList'][0]['checked'] = True
# config["merged_process_data"] = merge_process_data()

# # ----------筛选视图部分------------
# @api_bp.route('/api/filter', methods=['GET'])
# def filter_info():
#     return jsonify(config['classList'])

# # ----------筛选班级部分------------
# @api_bp.route('/api/filter_classes', methods=['POST'])
# def merge_classes():
#     # 获取前端发送的数据，这里假设前端发送的是JSON格式的数据
#     data = request.get_json()
    
#     # 检查是否接收到有效的数据
#     if not data or 'classes' not in data:
#         return jsonify({'error': 'No classes provided'}), 400
    
#     # 获取班级列表
#     classes = data['classes']
#     # print(classes)
#     # 检查班级列表中的每个班级是否存在
#     for class_i in classes:
#         # print('class_i', class_i)
#         if class_i['id'] > 15 or class_i['id'] < 1:
#             return jsonify({"error": f"Class {class_i['id']} does not exist"}), 400
    
#     # 获取对应的DataFrame并合并
#     contact_df = fs.contact_data(classes)
    
#     # 将合并后的DataFrame转换为JSON格式
#     config['all_class_df'] = contact_df
#     config['classList'] = classes
#     config['merged_process_data'] = merge_process_data()

#     # 更新所有相关类的 merged_process_data
#     cluster_routes.update_merged_process_data(config['merged_process_data'])
#     student_routes.update_all_class_df(config['merged_process_data'])
#     question_routes.update_merged_process_data(config['all_class_df'])
#     week_routes.update_merged_process_data(config['merged_process_data'])

#     # 返回处理后的结果
#     response = {
#         'data': classes,
#         'message': 'Classes have been successfully merged.'
#     }
    
#     return jsonify(response)

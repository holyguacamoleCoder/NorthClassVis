from flask import request, jsonify
from tools import fileSystem as fs
from tools.config import Config
from tools.features import PreliminaryFeatureCalculator, FinalFeatureCalculator
from tools.pca_analysis import PCAAnalysis
from tools.cluster_analysis import ClusterAnalysis
from routes.scatter_routes import ScatterRoutes
from routes.portrait_routes import PortraitRoutes
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
        contact_df = fs.contact_data(fs.class_dir, classes)

        # 将合并后的DataFrame转换为JSON格式
        self.config.all_class_df = contact_df
        self.config.classList = classes
        self.config.merged_process_data = self.config.merge_process_data()

        # 更新所有相关类的 merged_process_data
        pca_routes.update_merged_process_data(self.config.merged_process_data)
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

# 创建 PreliminaryFeatureCalculator 和 FinalFeatureCalculator 计算连接件
preliminary_feature_calculator = PreliminaryFeatureCalculator(config.get_merged_process_data())
feature_bonus = FinalFeatureCalculator(preliminary_feature_calculator.get_features(), ['student_ID']).get_result()
feature_knowledge = FinalFeatureCalculator(preliminary_feature_calculator.get_features(), ['student_ID', 'knowledge']).get_result()

# 创建 PCAAnalysis 实例
pca_analysis = PCAAnalysis(feature_bonus)

# 创建 CLusterAnalysis 实例
cluster_analysis = ClusterAnalysis(
    students_data=pca_analysis.get_transformed_data().to_dict(orient='index'))

# 创建 Routes 实例
config_routes = ConfigRoutes(config)

pca_routes = ScatterRoutes(
    config=config, 
    pca_analysis=pca_analysis, 
    cluster_analysis=cluster_analysis)

cluster_routes = PortraitRoutes(
    config=config, 
    cluster_analysis=cluster_analysis,
    feature_bonus=feature_bonus,
    feature_knowledge=feature_knowledge)

student_routes = StudentRoutes(config)
question_routes = QuestionRoutes(config)
week_routes = WeekRoutes(config)

# 注册 Blueprint 蓝图
config_routes.api_bp.register_blueprint(cluster_routes.cluster_bp, url_prefix='/api')
config_routes.api_bp.register_blueprint(pca_routes.pca_bp, url_prefix='/api')
config_routes.api_bp.register_blueprint(student_routes.student_bp, url_prefix='/api')
config_routes.api_bp.register_blueprint(question_routes.question_bp, url_prefix='/api')
config_routes.api_bp.register_blueprint(week_routes.week_bp, url_prefix='/api')

# 暴露 api_bp 变量
api_bp = config.get_api_bp()


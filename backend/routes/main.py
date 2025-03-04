from flask import request, jsonify
from tools import fileSystem as fs
from tools.config import Config
from tools.features import PreliminaryFeatureCalculator, FinalFeatureCalculator
from tools.pca_analysis import PCAAnalysis
from tools.cluster_analysis import ClusterAnalysis

from routes.pca_routes import PCARoutes
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
# 创建 PreliminaryFeatureCalculator 和 FinalFeatureCalculator 实例
preliminary_feature_calculator = PreliminaryFeatureCalculator(config.get_merged_process_data())
final_feature_calculator_bonus = FinalFeatureCalculator(preliminary_feature_calculator.get_features(), ['student_ID'])
final_feature_calculator_knowledge = FinalFeatureCalculator(preliminary_feature_calculator.get_features(), ['student_ID', 'knowledge'])

# 创建 PCAAnalysis 实例
pca_analysis = PCAAnalysis(
    preliminary_feature_calculator=preliminary_feature_calculator,
    final_feature_calculator=final_feature_calculator_bonus)

# 创建 CLusterAnalysis 实例
cluster_analysis = ClusterAnalysis(pca_analysis.get_transformed_data().to_dict(orient='index'))

# 创建 ConfigRoutes 实例
config_routes = ConfigRoutes(config)

# 注册 cluster 蓝图
cluster_routes = ClusterRoutes(config, cluster_analysis)
config_routes.api_bp.register_blueprint(cluster_routes.cluster_bp, url_prefix='/api')

# 注册PCA路由
pca_routes = PCARoutes(config, 
                       pca_analysis=pca_analysis, 
                       cluster_analysis=cluster_analysis)
config_routes.api_bp.register_blueprint(pca_routes.pca_bp, url_prefix='/api')

# 注册 student 蓝图
student_routes = StudentRoutes(config)
config_routes.api_bp.register_blueprint(student_routes.student_bp, url_prefix='/api')

# 注册 question 蓝图
question_routes = QuestionRoutes(config)
config_routes.api_bp.register_blueprint(question_routes.question_bp, url_prefix='/api')

# 注册 week 蓝图
week_routes = WeekRoutes(config)
config_routes.api_bp.register_blueprint(week_routes.week_bp, url_prefix='/api')

api_bp = config.get_api_bp()


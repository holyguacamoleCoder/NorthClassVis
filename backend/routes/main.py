from tools.config import Config
from tools.features import PreliminaryFeatureCalculator, FinalFeatureCalculator
from tools.pca_analysis import PCAAnalysis
from tools.cluster_analysis import ClusterAnalysis
from routes.nav_routes import NavRoutes
from routes.scatter_routes import ScatterRoutes
from routes.portrait_routes import PortraitRoutes
from routes.student_routes import StudentRoutes
from routes.question_routes import QuestionRoutes
from routes.week_routes import WeekRoutes

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
nav_routes = NavRoutes(config)
scatter_routes = ScatterRoutes(
    config=config, 
    pca_analysis=pca_analysis, 
    cluster_analysis=cluster_analysis)
portrait_routes = PortraitRoutes(
    config=config, 
    cluster_analysis=cluster_analysis,
    feature_bonus=feature_bonus,
    feature_knowledge=feature_knowledge)
student_routes = StudentRoutes(config)
question_routes = QuestionRoutes(config)
week_routes = WeekRoutes(config)

# 注册 Blueprint 蓝图
config.api_bp.register_blueprint(nav_routes.nav_bp, url_prefix='/api')
config.api_bp.register_blueprint(scatter_routes.scatter_bp, url_prefix='/api')
config.api_bp.register_blueprint(portrait_routes.portrait_bp, url_prefix='/api')
config.api_bp.register_blueprint(student_routes.student_bp, url_prefix='/api')
config.api_bp.register_blueprint(question_routes.question_bp, url_prefix='/api')
config.api_bp.register_blueprint(week_routes.week_bp, url_prefix='/api')

# 暴露 api_bp 变量
api_bp = config.get_api_bp()


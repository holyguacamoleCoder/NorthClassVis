from tools.config import Config
from tools.feature_factory import FeatureFactory
from routes.nav_routes import NavRoutes
from routes.scatter_routes import ScatterRoutes
from routes.portrait_routes import PortraitRoutes
from routes.student_routes import StudentRoutes
from routes.question_routes import QuestionRoutes
from routes.week_routes import WeekRoutes

# 创建 Config 实例
config = Config()

# 创建 FeatureFactory 实例
feature_factory = FeatureFactory(config)

# 创建 Routes 实例
nav_routes = NavRoutes(config)
scatter_routes = ScatterRoutes(feature_factory)
portrait_routes = PortraitRoutes(feature_factory) 
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

# 添加观察者
config.add_observer(feature_factory)
config.add_observer(student_routes)
config.add_observer(question_routes)
config.add_observer(week_routes)

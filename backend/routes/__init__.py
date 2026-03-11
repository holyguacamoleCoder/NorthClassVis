from config.app_config import Config
from domain.features.factory import FeatureFactory
from routes.nav_routes import NavRoutes
from routes.scatter_routes import ScatterRoutes
from routes.portrait_routes import PortraitRoutes
from routes.student_routes import StudentRoutes
from routes.question_routes import QuestionRoutes
from routes.week_routes import WeekRoutes
import threading

# 延迟初始化包装器
class LazyFeatureFactory:
    """
    延迟初始化 FeatureFactory，避免在启动时立即执行耗时的特征计算。
    只有在首次访问时才真正创建 FeatureFactory 实例。
    """
    def __init__(self, config):
        self.config = config
        self._factory = None  # 不立即创建
        self._lock = threading.Lock()  # 线程锁，确保多线程安全
        self._initializing = False
    
    def _ensure_initialized(self):
        """确保 FeatureFactory 已初始化（线程安全）"""
        if self._factory is None and not self._initializing:
            with self._lock:
                # 双重检查，避免多个线程同时初始化
                if self._factory is None and not self._initializing:
                    self._initializing = True
                    try:
                        # 首次访问时才创建真正的 FeatureFactory
                        self._factory = FeatureFactory(self.config)
                    finally:
                        self._initializing = False
    
    def __getattr__(self, name):
        """
        当访问任何属性时，先确保 FeatureFactory 已初始化。
        这实现了延迟初始化的核心机制。
        """
        self._ensure_initialized()
        if self._factory is None:
            raise RuntimeError("FeatureFactory is still initializing. Please try again.")
        return getattr(self._factory, name)
    
    def update_data(self, new_config):
        """实现观察者模式接口，用于配置更新时重新初始化"""
        with self._lock:
            self.config = new_config
            # 如果已经初始化，需要重新初始化
            if self._factory is not None:
                self._factory.update_data(new_config)

# 创建 Config 实例（只加载配置，约1秒）
config = Config()

# 创建延迟初始化的 FeatureFactory 包装器（瞬间完成，不执行计算）
feature_factory = LazyFeatureFactory(config)
# feature_factory = FeatureFactory(config)

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

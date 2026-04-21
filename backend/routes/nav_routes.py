from flask import Blueprint, jsonify, request

from services import nav_service


class NavRoutes:
    def __init__(self, config):
        self.config = config
        self.nav_bp = Blueprint('nav', __name__)
        # 注册路由
        self.nav_bp.add_url_rule('/nav/filter', view_func=self.config_info, methods=['GET'])
        self.nav_bp.add_url_rule('/nav/config', view_func=self.process_classes, methods=['POST'])

    def config_info(self):
        min_week, max_week = self.config.get_week_extent()
        selected = self.config.get_week_range()
        if selected is None and max_week >= min_week:
            selected = [max(min_week, max_week - 15), max_week]
        return jsonify(
            {
                "classes": self.config.get_class_list(),
                "majors": self.config.get_majors(),
                "week_range": {
                    "min": min_week,
                    "max": max_week,
                    "selected": selected,
                },
            }
        )
    
    def process_classes(self):
        # 获取前端发送的数据，这里假设前端发送的是JSON格式的数据
        data = request.get_json()

        # 检查是否接收到有效的数据
        if not data or 'classes' not in data or 'majors' not in data:
            return self._error_response("No classes or majors provided", "INVALID_CONFIG_PAYLOAD", 400)

        # 获取班级列表和专业列表
        classes = data['classes']
        majors = data['majors']
        try:
            nav_service.apply_nav_config(
                config=self.config,
                classes=classes,
                majors=majors,
                week_range=data.get("week_range"),
            )
        except Exception as exc:
            return self._error_response(f"Failed to apply nav config: {exc}", "NAV_CONFIG_APPLY_FAILED", 500)

        return jsonify({'message': 'Classes have been successfully processed and filtered.'}), 200

    def _error_response(self, message, code, status):
        return jsonify({"error": message, "code": code}), status
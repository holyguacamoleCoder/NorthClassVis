from flask import Blueprint, jsonify, request

from core import data_loader

class NavRoutes:
    def __init__(self, config):
        self.config = config
        self.nav_bp = Blueprint('nav', __name__)
        # 注册路由
        self.nav_bp.add_url_rule('/nav/filter', view_func=self.config_info, methods=['GET'])
        self.nav_bp.add_url_rule('/nav/config', view_func=self.process_classes, methods=['POST'])

    def config_info(self):
        return jsonify(
            {
                "classes": self.config.get_class_list(),
                "majors": self.config.get_majors(),
            }
        )
    
    def process_classes(self):
        # 获取前端发送的数据，这里假设前端发送的是JSON格式的数据
        data = request.get_json()

        # 检查是否接收到有效的数据
        if not data or 'classes' not in data or 'majors' not in data:
            return jsonify({'error': 'No classes or majors provided'}), 400

        # 获取班级列表和专业列表
        classes = data['classes']
        majors = data['majors']

        # 获取对应的DataFrame并合并
        contacted_df = data_loader.load_submissions_by_classes(data_loader.SUBMISSIONS_DIR, classes)

        merged_df = data_loader.merge_dataframes_or_files(
            left_df=contacted_df,
            right_path=data_loader.STUDENT_INFO_PATH,
            on="student_ID",
            right_columns=["student_ID", "major"],
        )

        # 根据majors参数筛选对应majors数据
        filtered_df = merged_df[merged_df['major'].isin(majors)]

        # 更新配置
        self.config.set_class_list(classes)
        self.config.set_majors(majors)
        self.config.set_submissions_df(filtered_df)
        self.config.set_submissions_with_knowledge_df(self.config.merge_submissions_with_titles())
        
        # 通知 FeatureFactory 重新初始化依赖对象
        self.config.notify_observers()

        return jsonify({'message': 'Classes have been successfully processed and filtered.'}), 200
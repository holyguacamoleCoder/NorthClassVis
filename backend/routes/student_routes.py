from flask import Blueprint, jsonify, request

from core import data_loader
from services import student_service

class StudentRoutes:
    def __init__(self, config):
        self.config = config
        self.submissions_df = self.config.get_submissions_df()
        self.student_bp = Blueprint('student', __name__)
        self.register_routes()

    def register_routes(self):
        self.student_bp.add_url_rule('/student/submissions', view_func=self.get_submissions, methods=['GET'])
        self.student_bp.add_url_rule('/student/tree_data', view_func=self.get_tree_data, methods=['GET'])

    def update_data(self, new_config):
        self.config = new_config
        self.submissions_df = self.config.get_submissions_df()
    def get_submissions(self):
        df = self.submissions_df
        if df is None:
            return jsonify({"error": "Failed to load submissions data."}), 500

        # 获取查询参数
        student_id = request.args.get('studentID')
        title_id = request.args.get('titleID')
        limit = request.args.get('limit')

        # 过滤数据
        filtered_records = df.copy()
        if student_id:
            filtered_records = filtered_records[
                filtered_records["student_ID"].astype(str) == str(student_id)
            ]
        if title_id:
            filtered_records = filtered_records[
                filtered_records["title_ID"].astype(str) == str(title_id)
            ]

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

    def get_tree_data(self):
        df = self.submissions_df
        student_ids = request.args.getlist('student_ids[]')
        limit = request.args.get('limit')

        if df is None:
            return jsonify({'error': 'Failed to load data.'}), 500
        if student_ids:
            df = df[df['student_ID'].isin(student_ids)]
        # 转换数据
        student_info = data_loader.load_data(data_loader.STUDENT_INFO_PATH)
        tree_data = student_service.build_student_tree(df, student_info)
        
        if limit:
            try:
                limit = int(limit)
                # 限制根节点下的子节点数量
                tree_data['children'] = tree_data['children'][:limit]
            except ValueError:
                return jsonify({"error": "Invalid limit parameter."}), 400

        return jsonify(tree_data)
from flask import Blueprint, request, jsonify
from tools import fileSystem as fileSystem
from tools import StudentView as sv

class StudentRoutes:
    def __init__(self, config):
        self.config = config
        self.class_df_filtered_majors = self.config.get_class_df_filtered_majors()
        self.student_bp = Blueprint('student', __name__)
        self.register_routes()

    def register_routes(self):
        self.student_bp.add_url_rule('/student/submissions', view_func=self.get_submissions, methods=['GET'])
        self.student_bp.add_url_rule('/student/tree_data', view_func=self.get_tree_data, methods=['GET'])

    def update_data(self, new_config):
        self.config = new_config
        self.class_df_filtered_majors = self.config.get_class_df_filtered_majors()
    def get_submissions(self):
        df = self.class_df_filtered_majors
        if df is None:
            return jsonify({"error": "Failed to load submissions data."}), 500

        # 获取查询参数
        student_id = request.args.get('studentID')
        title_id = request.args.get('titleID')
        limit = request.args.get('limit')

        # 过滤数据
        filtered_records = df.copy()
        if student_id:
            try:
                student_id = int(student_id)
                filtered_records = filtered_records[filtered_records['student_ID'] == student_id]
            except ValueError:
                return jsonify({"error": "Invalid studentID parameter."}), 400
        if title_id:
            try:
                title_id = int(title_id)
                filtered_records = filtered_records[filtered_records['title_ID'] == title_id]
            except ValueError:
                return jsonify({"error": "Invalid titleID parameter."}), 400

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
        df = self.class_df_filtered_majors
        limit = request.args.get('limit')

        if df is None:
            return jsonify({'error': 'Failed to load data.'}), 500

        # 转换数据
        student_info = fileSystem.load_data(fileSystem.studentFilename)
        tree_data = sv.transform_data(df, student_info)
        
        if limit:
            try:
                limit = int(limit)
                # 限制根节点下的子节点数量
                tree_data['children'] = tree_data['children'][:limit]
            except ValueError:
                return jsonify({"error": "Invalid limit parameter."}), 400

        return jsonify(tree_data)
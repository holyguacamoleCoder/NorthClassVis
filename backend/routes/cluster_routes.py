from flask import Blueprint, jsonify

class ClusterRoutes:
    def __init__(self, config, cluster_analysis):
        self.config = config
        self.cluster_analysis = cluster_analysis
        self.cluster_bp = Blueprint('cluster', __name__)
        self.register_routes()

    def register_routes(self):
        self.cluster_bp.add_url_rule('/cluster/centers', view_func=self.cluster_centers, methods=['GET'])
        self.cluster_bp.add_url_rule('/cluster/everyone', view_func=self.cluster_everyone, methods=['GET'])
        self.cluster_bp.add_url_rule('/cluster/students', view_func=self.cluster_center_students, methods=['GET'])

    def cluster_centers(self):
        return jsonify(self.cluster_analysis.get_cluster_centers())

    def cluster_everyone(self):
        return jsonify(self.cluster_analysis.get_student_clusters())

    def cluster_center_students(self):
        target_stu_info = self.cluster_analysis.get_cluster_center_students_ID()
        # 取出对应student_ID的'circular_bar'和'radar'数据
        result = {}
        for student_info in target_stu_info:
            student_ID = student_info['student_ID']
            cluster_index = student_info['cluster']
            result[student_ID] = {
                'cluster': cluster_index,
                'knowledge': self.cluster_analysis.raw_data.get(student_ID, None),
                'radar': self.cluster_analysis.raw_data.get(student_ID, None)
            }
        return jsonify(result)
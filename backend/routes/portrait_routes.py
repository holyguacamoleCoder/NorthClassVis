from flask import Blueprint, jsonify

class PortraitRoutes:
    def __init__(self, feature_factory):
        self.feature_factory = feature_factory
        self.portrait_bp = Blueprint('cluster', __name__)
        self.register_routes()
        # self.update_data()

    def register_routes(self):
        self.portrait_bp.add_url_rule('/cluster/centers', view_func=self.cluster_centers, methods=['GET'])
        self.portrait_bp.add_url_rule('/cluster/everyone', view_func=self.cluster_everyone, methods=['GET'])
        self.portrait_bp.add_url_rule('/cluster/students', view_func=self.cluster_center_students, methods=['GET'])

    def cluster_centers(self):
        return jsonify(self.feature_factory.cluster_analysis.get_cluster_centers())

    def cluster_everyone(self):
        return jsonify(self.feature_factory.cluster_analysis.get_student_clusters())

    def cluster_center_students(self):
        target_stu_info = self.feature_factory.cluster_analysis.get_cluster_center_students_ID()
        # 取出对应student_ID的'circular_bar'和'radar'数据
        result = {}
        for student_info in target_stu_info:
            student_ID = student_info['student_ID']
            cluster_index = student_info['cluster']
            # 获取df对应行并转为对应字典
            knowledge = self.feature_factory.feature_knowledge.loc[student_ID].to_dict()
            bonus = self.feature_factory.feature_bonus.loc[student_ID].to_dict()
            result[student_ID] = {
                'cluster': cluster_index,
                'knowledge': knowledge,
                'bonus': bonus
            }
        return jsonify(result)
    
    # 以下弃用，使用依赖注入而非观察者模式
    # def update_data(self):
    #     self.cluster_analysis = self.feature_factory.cluster_analysis
    #     self.feature_bonus = self.feature_factory.feature_bonus
    #     self.feature_knowledge = self.feature_factory.feature_knowledge

    # def cluster_center_students(self):
    #     self.update_data()
    #     target_stu_info = self.cluster_analysis.get_cluster_center_students_ID()
    #     # 取出对应student_ID的'circular_bar'和'radar'数据
    #     result = {}
    #     for student_info in target_stu_info:
    #         student_ID = student_info['student_ID']
    #         cluster_index = student_info['cluster']
    #         # 获取df对应行并转为对应字典
    #         knowledge = self.feature_knowledge.loc[student_ID].to_dict()
    #         bonus = self.feature_bonus.loc[student_ID].to_dict()
    #         result[student_ID] = {
    #             'cluster': cluster_index,
    #             'knowledge': knowledge,
    #             'bonus': bonus
    #         }
    #     return jsonify(result)
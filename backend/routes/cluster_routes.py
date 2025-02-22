# backend/cluster_routes.py
from flask import Blueprint, jsonify
from tools.features import PreliminaryFeatureCalculator, FinalFeatureCalculator
from tools.clustering import ClusterAnalysis

class ClusterRoutes:
    def __init__(self, merged_process_data):
        self.merged_process_data = merged_process_data
        self.raw_cluster_data = self.get_raw_cluster_data()
        self.cluster_bp = Blueprint('cluster', __name__)
        self.register_routes()

    def register_routes(self):
        self.cluster_bp.add_url_rule('/cluster/centers', view_func=self.cluster_analysis_centers, methods=['GET'])
        self.cluster_bp.add_url_rule('/cluster/everyone', view_func=self.cluster_analysis_everyone, methods=['GET'])
        self.cluster_bp.add_url_rule('/cluster/students', view_func=self.analysis_cluster_center_students, methods=['GET'])

    def get_raw_cluster_data(self):        
        pre_calculator = PreliminaryFeatureCalculator(self.merged_process_data)
        pre_calc_submit_records = pre_calculator.get_features()

        # 计算circular bar plot所需指标数据
        final_calculator_bar = FinalFeatureCalculator(pre_calc_submit_records, ['student_ID', 'knowledge'])
        final_result_bar = final_calculator_bar.calc_final_features()
       
        target_data_bar = final_result_bar.to_dict(orient='index')

        # 计算radar plot所需指标数据
        final_calculator_radar = FinalFeatureCalculator(pre_calc_submit_records, ['student_ID'])
        final_result_radar = final_calculator_radar.calc_final_features()
        target_data_radar = final_result_radar.to_dict(orient='index')

        return {
            'knowledge': target_data_bar, # 按学生-知识点划分得分
            'radar': target_data_radar      # 按学生划分得分
        }
    def update_merged_process_data(self, new_merged_process_data):
        self.merged_process_data = new_merged_process_data
        self.raw_cluster_data = self.get_raw_cluster_data()  # 重新计算 raw_cluster_data

    def cluster_analysis_centers(self):
        cluster_analysis = ClusterAnalysis(self.raw_cluster_data['radar'])
        return jsonify(cluster_analysis.get_cluster_centers())

    def cluster_analysis_everyone(self):
        cluster_analysis = ClusterAnalysis(self.raw_cluster_data['radar'])
        return jsonify(cluster_analysis.get_student_clusters())

    def analysis_cluster_center_students(self):
        cluster_analysis = ClusterAnalysis(self.raw_cluster_data['radar'])
        target_stu_info = cluster_analysis.get_cluster_center_students_ID()
        # 取出对应student_ID的'circular_bar'和'radar'数据
        result = {}
        for student_info in target_stu_info:
            student_ID = student_info['student_ID']
            cluster_index = student_info['cluster']
            result[student_ID] = {
                'cluster': cluster_index,
                'knowledge': self.raw_cluster_data['knowledge'].get(student_ID, None),
                'radar': self.raw_cluster_data['radar'].get(student_ID, None)
            }
        return jsonify(result)
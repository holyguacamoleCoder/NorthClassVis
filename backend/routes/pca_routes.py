# pca_routes.py
from flask import Blueprint, jsonify
import pandas as pd
from tools.features import PreliminaryFeatureCalculator, FinalFeatureCalculator
from tools.clustering import ClusterAnalysis
from tools.pca_analysis import PCAAnalysis

class PCARoutes:
    def __init__(self, merged_process_data):
        self.merged_process_data = merged_process_data
        self.raw_pca_data = self.get_raw_pca_data()
        self.pca_bp = Blueprint('pca', __name__)
        self.register_routes()

    def register_routes(self):
        self.pca_bp.add_url_rule('/pca/scatter', view_func=self.pca_cluster, methods=['GET'])

    def get_raw_pca_data(self):
        pre_calculator = PreliminaryFeatureCalculator(self.merged_process_data)
        pre_calc_submit_records = pre_calculator.get_features()

        # 计算radar plot所需指标数据
        final_calculator_radar = FinalFeatureCalculator(pre_calc_submit_records, ['student_ID'])
        final_result_radar = final_calculator_radar.calc_final_features()
        target_data_radar = final_result_radar

        return target_data_radar

    def update_merged_process_data(self, new_merged_process_data):
        self.merged_process_data = new_merged_process_data
        self.raw_pca_data = self.get_raw_pca_data()  # 重新计算 raw_pca_data

    def pca_cluster(self):
        # PCA分析
        pca_analysis = PCAAnalysis(self.raw_pca_data)
        transformed_data = pca_analysis.get_transformed_data()
        transformed_data.index = self.raw_pca_data.index  # 确保索引一致

        # 聚类分析
        cluster_analysis = ClusterAnalysis(transformed_data.to_dict(orient='index'), n_clusters=3)
        student_clusters = cluster_analysis.get_student_clusters()

        # 合并聚类结果和PCA结果
        result = []
        for student_id, cluster_info in student_clusters.items():
            cluster = cluster_info['cluster']
            transformed_point = transformed_data.loc[student_id].to_dict()
            result.append({
                'student_id': student_id,
                'cluster': cluster,
                'transform': transformed_point
            })

        return jsonify(result)
# backend/cluster_routes.py
from flask import Blueprint, request, jsonify
from tools import ParallelView as pv
from tools.clustering import ClusterAnalysis

class ClusterRoutes:
    def __init__(self, merged_process_data):
        self.merged_process_data = merged_process_data
        self.cluster_bp = Blueprint('cluster', __name__)
        self.register_routes()

    def register_routes(self):
        self.cluster_bp.add_url_rule('/cluster/centers', view_func=self.cluster_analysis_centers, methods=['GET'])
        self.cluster_bp.add_url_rule('/cluster/everyone', view_func=self.cluster_analysis_everyone, methods=['GET'])
        self.cluster_bp.add_url_rule('/cluster/students', view_func=self.get_student_clusters, methods=['GET'])

    def get_raw_cluster_data(self, stu=None, every=None):
        all_submit_records = self.merged_process_data()
        final_scores = pv.calc_final_scores(pv.parallel_calculate_features(all_submit_records), ['student_ID', 'knowledge'])
        target_data = final_scores.to_dict(orient='index')
        return target_data

    def cluster_analysis_centers(self):
        stu = request.args.get('stu')
        every = request.args.get('every')

        cluster_analysis = ClusterAnalysis(self.get_raw_cluster_data(stu=stu, every=every))
        return jsonify(cluster_analysis.get_cluster_centers())

    def cluster_analysis_everyone(self):
        stu = request.args.get('stu')
        every = request.args.get('every')

        cluster_analysis = ClusterAnalysis(self.get_raw_cluster_data(stu=stu, every=every))
        return jsonify(cluster_analysis.get_student_clusters())

    def get_student_clusters(self):
        stu = request.args.get('stu')
        every = request.args.get('every')

        cluster_analysis = ClusterAnalysis(self.get_raw_cluster_data(stu=stu, every=every))
        return jsonify(cluster_analysis.get_cluster_center_students())
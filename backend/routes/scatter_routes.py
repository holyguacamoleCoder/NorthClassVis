from flask import Blueprint, jsonify

class ScatterRoutes:
    def __init__(self, config, pca_analysis, cluster_analysis):
        self.config = config
        self.pca_analysis = pca_analysis
        self.cluster_analysis = cluster_analysis
        self.pca_bp = Blueprint('pca', __name__)
        self.register_routes()

    def register_routes(self):
        self.pca_bp.add_url_rule('/pca/scatter', view_func=self.pca_cluster, methods=['GET'])

    def pca_cluster(self):
        # 获取PCA变换后的数据
        transformed_data = self.pca_analysis.get_transformed_data()
        transformed_data.index = self.pca_analysis.raw_pca_data.index  # 确保索引一致
       
        student_clusters = self.cluster_analysis.get_student_clusters()

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
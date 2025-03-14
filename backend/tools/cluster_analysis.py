import numpy as np
from sklearn.cluster import KMeans
import pandas as pd

class ClusterAnalysis:
    def __init__(self, students_data, n_clusters=3):
        self.raw_data = students_data
        self.n_clusters = n_clusters
        self.features_array = self.extract_features(self.raw_data)
        self.kmeans = self.create_kmeans_model(self.features_array, n_clusters)

    def extract_features(self, raw_data):
        # 提取特征向量
        features = []
        for student_id, values in raw_data.items():
            if isinstance(values, dict):
                feature_vector = list(values.values())
                features.append(feature_vector)
            else:
                raise ValueError(f"Invalid data format for student {student_id}: {values}")
        return np.array(features)

    def create_kmeans_model(self, features_array, n_clusters=3):
        # 创建KMeans实例
        kmeans = KMeans(n_clusters=n_clusters, max_iter=100, random_state=42)
        # 训练模型
        kmeans.fit(features_array)
        return kmeans

    def get_student_clusters(self):
        # 输出每个学生的聚类分配
        predictions = self.kmeans.predict(self.features_array)
        result = {}
        for student_id, prediction in zip(self.raw_data.keys(), predictions):
            result[student_id] = {
                "knowledge": self.raw_data[student_id],
                "cluster": int(prediction)
            }
        return result

    def get_cluster_center_students_ID(self):
        # 获取每个聚类中心最近的学生ID
        cluster_centers = self.kmeans.cluster_centers_
        cluster_center_students = []

        raw_data_df = pd.DataFrame(self.raw_data).T

        for center_index, center in enumerate(cluster_centers):
            # 找到距离每个聚类中心最近的学生
            closest_student = raw_data_df.apply(lambda row: np.linalg.norm(row - center), axis=1).idxmin()
            cluster_center_students.append({
                'student_ID': closest_student,
                'cluster': center_index
            })

        return cluster_center_students

    def get_cluster_centers(self):
        # 获取聚类中心
        cluster_centers = self.kmeans.cluster_centers_
        result = {}
        for i, center in enumerate(cluster_centers):
            result[str(i)] = {
                "cluster": i,
                "knowledge": dict(zip(self.raw_data[next(iter(self.raw_data))].keys(), center))
            }
        return result

if __name__ == "__main__":
  # 示例用法
  students_data = {
      'student1': {'math': 88, 'science': 92, 'english': 85},
      'student2': {'math': 75, 'science': 80, 'english': 78},
      'student3': {'math': 95, 'science': 90, 'english': 92},
      'student4': {'math': 60, 'science': 65, 'english': 68}
  }

  cluster_analysis = ClusterAnalysis(students_data)
  result_every = cluster_analysis.get_student_clusters()
  result_stu = cluster_analysis.get_cluster_center_students()
  result_centers = cluster_analysis.get_cluster_centers()

  print("Student Clusters:", result_every)
  print("Cluster Center Students:", result_stu)
  print("Cluster Centers:", result_centers)
import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import MinMaxScaler
import pandas as pd

class ClusterAnalysis:
    
    # def __init__(self, students_data, n_clusters=3):
    #     self.students_data = students_data
    #     self.n_clusters = n_clusters
    #     self.features_array = self.extract_features(students_data)
    #     self.kmeans = self.create_kmeans_model(self.features_array, n_clusters)

    _instance = None

    def __new__(cls, students_data=None, n_clusters=3):
        if not cls._instance or students_data != cls._instance.students_data:
            cls._instance = super(ClusterAnalysis, cls).__new__(cls)
            cls._instance.students_data = students_data
            cls._instance.n_clusters = n_clusters
            cls._instance.features_array = cls._instance.extract_features(students_data)
            cls._instance.kmeans = cls._instance.create_kmeans_model(cls._instance.features_array, n_clusters)
        return cls._instance

    def extract_features(self, students_data):
        # 提取特征向量
        features = []
        for student_id, values in students_data.items():
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
        for student_id, prediction in zip(self.students_data.keys(), predictions):
            result[student_id] = {
                "knowledge": self.students_data[student_id],
                "cluster": int(prediction)
            }
        return result

    def get_cluster_center_students(self):
        # 获取每个聚类中心的学生对象
        cluster_centers = self.kmeans.cluster_centers_
        cluster_center_students = []

        students_data_df = pd.DataFrame(self.students_data).T

        for center in cluster_centers:
            # 找到距离每个聚类中心最近的学生
            closest_student = students_data_df.apply(lambda row: np.linalg.norm(row - center), axis=1).idxmin()
            cluster_center_students.append(closest_student)

        return cluster_center_students

    def get_cluster_centers(self):
        # 获取聚类中心
        cluster_centers = self.kmeans.cluster_centers_
        result = {}
        for i, center in enumerate(cluster_centers):
            result[str(i)] = {
                "cluster": i,
                "knowledge": dict(zip(self.students_data[next(iter(self.students_data))].keys(), center))
            }
        return result

    def analyze(self, stu=None, every=None):
        if every is not None:
            return self.get_student_clusters()

        if stu is not None:
            return self.get_cluster_center_students()

        return self.get_cluster_centers()
    
    @classmethod
    def reset_instance(cls, data=None, n_clusters=3):
        cls._instance = None
        return cls(data, n_clusters)

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
import numpy as np
import pandas as pd
from typing import Dict, List, Union

class ClusterAnalysis:
    def __init__(
        self,
        students_data: Dict[str, Dict[str, float]],
        method: str = "kmeans",
        n_clusters: int = 3,
        **kwargs
    ):
        """
        初始化聚类分析
        
        参数:
            students_data: 学生数据，格式为 {学生ID: {科目: 分数}}
            method: 聚类方法，支持 "kmeans", "dbscan", "agg", "gmm"
            n_clusters: 聚类数量（仅适用于 K-Means、Agglomerative、GMM）
            **kwargs: 传递给聚类算法的额外参数
        """
        self.raw_data = students_data
        self.method = method.lower()
        self.n_clusters = n_clusters
        self.kwargs = kwargs
        
        # 提取特征向量
        self.features_array = self.extract_features(self.raw_data)
        
        # 初始化聚类模型
        self.cluster_model = self.create_cluster_model(
            method=self.method,
            n_clusters=self.n_clusters,
            **self.kwargs
        )
        
        # 训练模型
        self.cluster_model.fit(self.features_array)

    def extract_features(self, raw_data: Dict[str, Dict[str, float]]) -> np.ndarray:
        """提取特征向量"""
        features = []
        for student_id, values in raw_data.items():
            if isinstance(values, dict):
                feature_vector = list(values.values())
                features.append(feature_vector)
            else:
                raise ValueError(f"Invalid data format for student {student_id}: {values}")
        return np.array(features)

    def create_cluster_model(self, method: str="kmeans", n_clusters: int = 3, **kwargs):
        """动态创建聚类模型"""
        method = method.lower()
        available_methods = {
            "kmeans": ("sklearn.cluster", "KMeans"),
            "dbscan": ("sklearn.cluster", "DBSCAN"),
            "agg": ("sklearn.cluster", "AgglomerativeClustering"),
            "gmm": ("sklearn.mixture", "GaussianMixture"),
        }
        
        if method not in available_methods:
            raise ValueError(
                f"未知的聚类方法: {method}。支持的方法: {', '.join(available_methods.keys())}"
            )
        
        module_name, class_name = available_methods[method]
        
        try:
            # 动态导入
            module = __import__(module_name, fromlist=[class_name])
            model_class = getattr(module, class_name)
            
            # 初始化聚类器（不同方法的参数可能不同）
            if method == "kmeans":
                return model_class(n_clusters=n_clusters, random_state=42, **kwargs)
            elif method == "dbscan":
                return model_class(**kwargs)  # DBSCAN 不需要 n_clusters
            elif method == "agg":
                return model_class(n_clusters=n_clusters, **kwargs)
            elif method == "gmm":
                return model_class(n_components=n_clusters, random_state=42, **kwargs)
        
        except ImportError as e:
            raise ImportError(
                f"无法导入 {method} 所需的库，请先安装。例如：\n"
                f"pip install scikit-learn\n"
            ) from e

    def get_student_clusters(self) -> Dict[str, Dict[str, Union[int, Dict[str, float]]]]:
        """获取每个学生的聚类分配"""
        if self.method == "gmm":
            predictions = self.cluster_model.predict(self.features_array)
        else:
            predictions = self.cluster_model.labels_
        
        result = {}
        for student_id, prediction in zip(self.raw_data.keys(), predictions):
            result[student_id] = {
                "knowledge": self.raw_data[student_id],
                "cluster": int(prediction)
            }
        return result

    def get_cluster_center_students_ID(self) -> List[Dict[str, Union[str, int]]]:
        """获取每个聚类中心最近的学生ID（仅适用于 K-Means/GMM）"""
        if self.method not in ["kmeans", "gmm"]:
            raise ValueError(f"{self.method} 不支持计算聚类中心！")
        
        if self.method == "kmeans":
            cluster_centers = self.cluster_model.cluster_centers_
        else:  # GMM
            cluster_centers = self.cluster_model.means_
        
        raw_data_df = pd.DataFrame(self.raw_data).T
        cluster_center_students = []
        
        for center_index, center in enumerate(cluster_centers):
            closest_student = raw_data_df.apply(
                lambda row: np.linalg.norm(row - center), axis=1
            ).idxmin()
            cluster_center_students.append({
                'student_ID': closest_student,
                'cluster': center_index
            })
        
        return cluster_center_students

    def get_cluster_centers(self) -> Dict[str, Dict[str, Union[int, Dict[str, float]]]]:
        """获取聚类中心（仅适用于 K-Means/GMM）"""
        if self.method not in ["kmeans", "gmm"]:
            raise ValueError(f"{self.method} 不支持计算聚类中心！")
        
        if self.method == "kmeans":
            centers = self.cluster_model.cluster_centers_
        else:  # GMM
            centers = self.cluster_model.means_
        
        result = {}
        for i, center in enumerate(centers):
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

    # 使用 K-Means（默认）
    kmeans_analysis = ClusterAnalysis(students_data, method="kmeans", n_clusters=2)
    print("K-Means 聚类结果:", kmeans_analysis.get_student_clusters())

    # 使用 DBSCAN（不需要 n_clusters）
    dbscan_analysis = ClusterAnalysis(students_data, method="dbscan", eps=10, min_samples=2)
    print("DBSCAN 聚类结果:", dbscan_analysis.get_student_clusters())

    # 使用 GMM
    gmm_analysis = ClusterAnalysis(students_data, method="gmm", n_clusters=2)
    print("GMM 聚类中心:", gmm_analysis.get_cluster_centers())
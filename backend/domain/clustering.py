from typing import Dict, List, Union

import numpy as np


class ClusterAnalysis:
    def __init__(
        self,
        students_data: Dict[str, Dict[str, float]],
        method: str = "kmeans",
        n_clusters: int = 3,
        **kwargs,
    ):
        self.raw_data = students_data
        self.method = method.lower()
        self.n_clusters = n_clusters
        self.kwargs = kwargs
        self.features_array = self.extract_features(self.raw_data)
        self.cluster_model = self.create_cluster_model(
            method=self.method,
            n_clusters=self.n_clusters,
            **self.kwargs,
        )
        self.cluster_model.fit(self.features_array)

    def extract_features(self, raw_data: Dict[str, Dict[str, float]]) -> np.ndarray:
        features = []
        for student_id, values in raw_data.items():
            if not isinstance(values, dict):
                raise ValueError(f"Invalid data format for student {student_id}: {values}")
            features.append(list(values.values()))
        return np.array(features)

    def create_cluster_model(self, method: str = "kmeans", n_clusters: int = 3, **kwargs):
        method = method.lower()
        available_methods = {
            "kmeans": ("domain.algorithms.kmeans", "MyKMeans"),
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
            module = __import__(module_name, fromlist=[class_name])
            model_class = getattr(module, class_name)
            if method == "kmeans":
                return model_class(n_clusters=n_clusters, random_state=42, **kwargs)
            if method == "dbscan":
                return model_class(**kwargs)
            if method == "agg":
                return model_class(n_clusters=n_clusters, **kwargs)
            return model_class(n_components=n_clusters, random_state=42, **kwargs)
        except ImportError as exc:
            raise ImportError("无法导入所需的聚类库，请先安装 scikit-learn。") from exc

    def get_student_clusters(self) -> Dict[str, Dict[str, Union[int, Dict[str, float]]]]:
        predictions = (
            self.cluster_model.predict(self.features_array)
            if self.method == "gmm"
            else self.cluster_model.labels_
        )
        result = {}
        for student_id, prediction in zip(self.raw_data.keys(), predictions):
            result[student_id] = {
                "knowledge": self.raw_data[student_id],
                "cluster": int(prediction),
            }
        return result

    def get_cluster_center_students_ID(
        self,
        valid_student_ids: set[str] | None = None,
    ) -> List[Dict[str, Union[str, int]]]:
        if self.method not in ["kmeans", "gmm"]:
            raise ValueError(f"{self.method} 不支持计算聚类中心！")

        cluster_centers = (
            self.cluster_model.cluster_centers_
            if self.method == "kmeans"
            else self.cluster_model.means_
        )
        student_ids = list(self.raw_data.keys())
        valid = {str(s) for s in valid_student_ids} if valid_student_ids else None
        cluster_center_students = []

        for center_index, center in enumerate(cluster_centers):
            best_id: str | None = None
            best_dist = np.inf
            for row_index, student_id in enumerate(student_ids):
                sid = str(student_id)
                if valid is not None and sid not in valid:
                    continue
                row = self.features_array[row_index]
                dist = float(np.linalg.norm(row - center))
                if dist < best_dist:
                    best_dist = dist
                    best_id = sid
            if best_id is not None:
                cluster_center_students.append(
                    {"student_ID": best_id, "cluster": center_index}
                )

        return cluster_center_students

    def get_cluster_centers(self) -> Dict[str, Dict[str, Union[int, Dict[str, float]]]]:
        if self.method not in ["kmeans", "gmm"]:
            raise ValueError(f"{self.method} 不支持计算聚类中心！")

        centers = (
            self.cluster_model.cluster_centers_
            if self.method == "kmeans"
            else self.cluster_model.means_
        )

        result = {}
        first_student = next(iter(self.raw_data))
        knowledge_keys = self.raw_data[first_student].keys()
        for index, center in enumerate(centers):
            result[str(index)] = {
                "cluster": index,
                "knowledge": dict(zip(knowledge_keys, center)),
            }
        return result

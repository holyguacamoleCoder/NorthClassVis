# 自主实现K-means聚类
import numpy as np

class MyKMeans:
    def __init__(self, n_clusters=3, max_iter=300, random_state=None):
        self.n_clusters = n_clusters
        self.max_iter = max_iter
        self.random_state = random_state
        self.cluster_centers_ = None
        self.labels_ = None

    def _initialize_cluster_centers_(self, X):
        # 随机选择 K 个数据点作为初始中心点
        np.random.seed(self.random_state)
        indices = np.random.permutation(X.shape[0])[:self.n_clusters]
        return X[indices]

    def _compute_distances(self, X, cluster_centers_):
        # 计算每个点到所有中心点的距离（欧氏距离）
        distances = np.zeros((X.shape[0], self.n_clusters))
        for i in range(self.n_clusters):
            # axis=1 表示按行计算向量的模长（即每个样本到中心的距离）
            distances[:, i] = np.linalg.norm(X - cluster_centers_[i], axis=1)
        return distances

    def _assign_clusters(self, distances):
        # 分配每个点到最近的中心点所属的簇
        return np.argmin(distances, axis=1)

    def _update_cluster_centers_(self, X, labels):
        # 计算每个簇的新中心点（均值）
        new_cluster_centers_ = np.zeros((self.n_clusters, X.shape[1]))
        for i in range(self.n_clusters):
            new_cluster_centers_[i] = np.mean(X[labels == i], axis=0)
        return new_cluster_centers_

    def fit(self, X):
        # 1. 初始化中心点
        self.cluster_centers_ = self._initialize_cluster_centers_(X)

        for _ in range(self.max_iter):
            # 2. 计算距离并分配簇
            distances = self._compute_distances(X, self.cluster_centers_)
            labels = self._assign_clusters(distances)

            # 3. 更新中心点
            new_cluster_centers_ = self._update_cluster_centers_(X, labels)

            # 4. 检查是否收敛
            if np.allclose(self.cluster_centers_, new_cluster_centers_):
                break

            self.cluster_centers_ = new_cluster_centers_

        self.labels_ = self._assign_clusters(self._compute_distances(X, self.cluster_centers_))
        return self

    def predict(self, X):
        distances = self._compute_distances(X, self.cluster_centers_)
        return self._assign_clusters(distances)
    

if __name__ == "__main__":
  # 生成测试数据
  np.random.seed(42)
  X = np.random.rand(100, 2)  # 100个2维数据点
  print(X.shape[0])
  # MyK-Means
  my_kmeans = MyKMeans(n_clusters=3, random_state=42)
  my_kmeans.fit(X)
  my_centroid = my_kmeans.cluster_centers_
  print(my_kmeans.labels_)
  my_labels = my_kmeans.predict(X)


  # scikit-learn K-Means
  from sklearn.cluster import KMeans as KMeans
  sk_kmeans = KMeans(n_clusters=3, random_state=42)
  sk_kmeans.fit(X)
  sk_centroid = sk_kmeans.cluster_centers_
  sk_labels = sk_kmeans.predict(X)

  # 比较结果
  print("My K-Means 中心点:\n", my_centroid)
  print("sklearn K-Means 中心点:\n", sk_centroid)
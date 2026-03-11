import numpy as np


class MyKMeans:
    def __init__(self, n_clusters=3, max_iter=300, random_state=None):
        self.n_clusters = n_clusters
        self.max_iter = max_iter
        self.random_state = random_state
        self.cluster_centers_ = None
        self.labels_ = None

    def _initialize_cluster_centers_(self, X):
        np.random.seed(self.random_state)
        indices = np.random.permutation(X.shape[0])[: self.n_clusters]
        return X[indices]

    def _compute_distances(self, X, cluster_centers_):
        distances = np.zeros((X.shape[0], self.n_clusters))
        for index in range(self.n_clusters):
            distances[:, index] = np.linalg.norm(X - cluster_centers_[index], axis=1)
        return distances

    def _assign_clusters(self, distances):
        return np.argmin(distances, axis=1)

    def _update_cluster_centers_(self, X, labels):
        new_cluster_centers_ = np.zeros((self.n_clusters, X.shape[1]))
        for index in range(self.n_clusters):
            new_cluster_centers_[index] = np.mean(X[labels == index], axis=0)
        return new_cluster_centers_

    def fit(self, X):
        self.cluster_centers_ = self._initialize_cluster_centers_(X)

        for _ in range(self.max_iter):
            distances = self._compute_distances(X, self.cluster_centers_)
            labels = self._assign_clusters(distances)
            new_cluster_centers_ = self._update_cluster_centers_(X, labels)
            if np.allclose(self.cluster_centers_, new_cluster_centers_):
                break
            self.cluster_centers_ = new_cluster_centers_

        self.labels_ = self._assign_clusters(
            self._compute_distances(X, self.cluster_centers_)
        )
        return self

    def predict(self, X):
        distances = self._compute_distances(X, self.cluster_centers_)
        return self._assign_clusters(distances)

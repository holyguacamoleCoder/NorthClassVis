# 自主实现PCA
import numpy as np

class MyPCA:
    def __init__(self, n_components):
        self.n_components = n_components
        self.components = None  # 主成分（特征向量）
        self.mean = None        # 数据的均值（用于标准化）
    
    def fit(self, X):
        # 1. 数据标准化（中心化）
        self.mean = np.mean(X, axis=0)
        X_centered = X - self.mean
        
        # 2. 计算协方差矩阵
        # rowvar=False表示每列是一个特征
        cov_matrix = np.cov(X_centered, rowvar=False)  
        
        # 3. 特征值分解
        eigenvalues, eigenvectors = np.linalg.eigh(cov_matrix)
        
        # 4. 按特征值降序排序，选择前n_components个主成分

        # np.argsort(eigenvalues) 返回从小到大排序的索引；
        # [::-1] 反转顺序得到从大到小的索引；
        sorted_indices = np.argsort(eigenvalues)[::-1]
        
        self.components = eigenvectors[:, sorted_indices[:self.n_components]]
    
    def transform(self, X):
        # 将数据投影到主成分空间
        X_centered = X - self.mean
        return np.dot(X_centered, self.components)
    
    def fit_transform(self, X):
        self.fit(X)
        return self.transform(X)
    
if __name__ == "__main__":
  from sklearn.decomposition import PCA as PCA
  from sklearn.datasets import load_iris
  
  # 加载数据
  data = load_iris()
  X = data.data
  
  # 自定义PCA
  my_pca = MyPCA(n_components=2)
  X_my = my_pca.fit_transform(X)
  
  # scikit-learn PCA
  sk_pca = PCA(n_components=2)
  X_sk = sk_pca.fit_transform(X)
  
  # 验证结果是否一致（允许微小误差）
  print("MyPCA结果:\n", X_my[:5])
  print("sklearn PCA结果:\n", X_sk[:5])
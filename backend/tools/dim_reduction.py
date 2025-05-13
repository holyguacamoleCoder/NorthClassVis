import pandas as pd

class DimReduction:
    def __init__(self, final_feature_calculator):
        self.final_feature_calculator = final_feature_calculator
        self.raw_pca_data = self.get_raw_dim_data()

    def get_raw_dim_data(self):
        return self.final_feature_calculator
    def get_transformed_data(self, method="pca", **kwargs):
        """支持选择性导入"""
        method = method.lower()
        available_methods = {
            # "pca": ("sklearn.decomposition", "PCA"),
            "pca": ("tools.MyPCA", "MyPCA"),
            "tsne": ("sklearn.manifold", "TSNE"),
            "umap": ("umap", "UMAP"),
            "lle": ("sklearn.manifold", "LocallyLinearEmbedding"),
            "mds": ("sklearn.manifold", "MDS"),
            "isomap": ("sklearn.manifold", "Isomap"),
        }

        if method not in available_methods:
            raise ValueError(
                f"未知的降维方法: {method}。支持的方法: {', '.join(available_methods.keys())}"
            )

        module_name, class_name = available_methods[method]

        try:
            # 动态导入
            module = __import__(module_name, fromlist=[class_name])
            transformer_class = getattr(module, class_name)

            # 初始化降维器
            transformer = transformer_class(n_components=2, **kwargs)

            # 执行降维
            transformed_data = transformer.fit_transform(self.raw_pca_data)

            # 将数据缩放到 [-5, 5], 便于前端统一视口渲染
            from sklearn.preprocessing import MinMaxScaler
            scaler = MinMaxScaler(feature_range=(-5, 5))
            scaled_data = scaler.fit_transform(transformed_data)

            return pd.DataFrame(
                scaled_data,
                index=self.raw_pca_data.index,
                columns=['x', 'y']
            )

        except ImportError as e:
            raise ImportError(
                f"无法导入 {method} 所需的库，请先安装。例如：\n"
                f"pip install scikit-learn   # PCA, t-SNE, LLE, MDS, Isomap\n"
                f"pip install umap-learn     # UMAP\n"
            ) from e
    
if __name__ == "__main__":
  # 示例用法
  # features_df是从features.py中计算得出的特征DataFrame
  features_df = pd.DataFrame({
      'student_ID': ['01d8aa21ef476b66c573', '03aa0b20dd4af1888eef', 'student3', 'student4'],
      'score_bonus': [1.0, 0.8, 0.9, 0.7],
      'tc_bonus': [0.5, 0.3, 0.4, 0.2],
      'mem_bonus': [0.6, 0.4, 0.5, 0.3],
      'error_type_penalty': [0.1, 0.2, 0.1, 0.3],
      'test_num_penalty': [1, 2, 1, 3],
      'rank_bonus': [2, 1, 3, 4],
      'explore_bonus': [0, 1, 0, 2],
      'enthusiasm_bonus': [0.8, 0.7, 0.9, 0.6]
  })
  
  dimReduction_analysis = DimReduction(features_df)
  transformed_data = dimReduction_analysis.get_transformed_data()
  
  print("Transformed Data:\n", transformed_data)
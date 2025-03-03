import numpy as np
import pandas as pd
from sklearn.decomposition import PCA

class PCAAnalysis:
    _instance = None

    def __new__(cls, features_df=None):
        if not cls._instance or not features_df.equals(cls._instance.raw_data):
            cls._instance = super(PCAAnalysis, cls).__new__(cls)
            cls._instance.raw_data = features_df
            cls._instance.student_ids = features_df.get('student_ID', None)
            if cls._instance.student_ids is not None:
                cls._instance.features_only_df = features_df.drop(columns=['student_ID'])
            else:
                cls._instance.features_only_df = features_df
            cls._instance.pca_model = cls._instance.create_pca_model(cls._instance.features_only_df)
            cls._instance.transformed_data = cls._instance.transform_features(cls._instance.features_only_df, cls._instance.pca_model)
            if cls._instance.student_ids is not None:
                cls._instance.transformed_data['student_ID'] = cls._instance.student_ids.values
        return cls._instance

    def create_pca_model(self, features_df):
        # 创建PCA实例
        pca = PCA(n_components=2)
        # 训练模型
        pca.fit(features_df)
        return pca

    def transform_features(self, features_df, pca_model):
        # 使用PCA模型转换特征
        transformed_features = pca_model.transform(features_df)
        return pd.DataFrame(transformed_features, columns=['x', 'y'])

    def get_transformed_data(self):
        # 输出转换后的特征
        return self.transformed_data

    @classmethod
    def reset_instance(cls, data=None):
        cls._instance = None
        return cls(data)
    
if __name__ == "__main__":
  # 示例用法
  # 假设features_df是从features.py中计算得出的特征DataFrame
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
  
  pca_analysis = PCAAnalysis(features_df)
  transformed_data = pca_analysis.get_transformed_data()
  
  print("Transformed Data:\n", transformed_data)
import pandas as pd


class DimReduction:
    def __init__(self, final_feature_calculator):
        self.final_feature_calculator = final_feature_calculator
        self.raw_pca_data = self.get_raw_dim_data()

    def get_raw_dim_data(self):
        return self.final_feature_calculator

    def get_transformed_data(self, method="pca", **kwargs):
        method = method.lower()
        available_methods = {
            "pca": ("domain.algorithms.pca", "MyPCA"),
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
            module = __import__(module_name, fromlist=[class_name])
            transformer_class = getattr(module, class_name)
            transformer = transformer_class(n_components=2, **kwargs)
            transformed_data = transformer.fit_transform(self.raw_pca_data)

            from sklearn.preprocessing import MinMaxScaler

            scaler = MinMaxScaler(feature_range=(-5, 5))
            scaled_data = scaler.fit_transform(transformed_data)
            return pd.DataFrame(
                scaled_data,
                index=self.raw_pca_data.index,
                columns=["x", "y"],
            )
        except ImportError as exc:
            raise ImportError(
                "无法导入所需的降维库，请先安装 scikit-learn 或 umap-learn。"
            ) from exc

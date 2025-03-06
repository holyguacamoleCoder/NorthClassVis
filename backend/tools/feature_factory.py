from tools.features import PreliminaryFeatureCalculator, FinalFeatureCalculator
from tools.pca_analysis import PCAAnalysis
from tools.cluster_analysis import ClusterAnalysis

class FeatureFactory:
    def __init__(self, config):
        self.config = config
        self.preliminary_feature_calculator = None
        self.feature_bonus = None
        self.feature_knowledge = None
        self.pca_analysis = None
        self.cluster_analysis = None
        self._initialize_features()

    def _initialize_features(self):
        self.preliminary_feature_calculator = PreliminaryFeatureCalculator(self.config.get_data_with_title_knowledge())
        features = self.preliminary_feature_calculator.get_features()
        self.feature_bonus = FinalFeatureCalculator(features, ['student_ID']).get_result()
        self.feature_knowledge = FinalFeatureCalculator(features, ['student_ID', 'knowledge']).get_result()

        self.pca_analysis = PCAAnalysis(self.feature_bonus)
        self.cluster_analysis = ClusterAnalysis(students_data=self.pca_analysis.get_transformed_data().to_dict(orient='index'))

    def update_data(self, new_config):
        self.config = new_config
        self._initialize_features()
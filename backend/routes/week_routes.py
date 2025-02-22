from flask import Blueprint, jsonify
from tools import WeekView as wv
from tools.features import PreliminaryFeatureCalculator, FinalFeatureCalculator

class WeekRoutes:
    def __init__(self, merged_process_data):
        self.merged_process_data = merged_process_data
        self.week_bp = Blueprint('week', __name__)
        self.register_routes()

    def register_routes(self):
        self.week_bp.add_url_rule('/week/week_data', view_func=self.week_analysis, methods=['GET'])

    def week_analysis(self):
        df = self.merged_process_data
        start_date = df['time'].min()
        df['week'] = df['time'].apply(lambda x: wv.calculate_week_of_year(x, start_date=start_date))
        
        pre_calculator = PreliminaryFeatureCalculator(df)
        pre_calc_submit_records = pre_calculator.get_features()

        # 计算每个学生的总分，不区分知识点
        final_calculator = FinalFeatureCalculator(pre_calc_submit_records, ['student_ID', 'week', 'knowledge'])
        final_result = final_calculator.calc_final_features()

        result =  final_result.to_dict(orient='index')
        
        result = wv.transform_data_for_visualization(result)
        return jsonify(result)
    
    def update_merged_process_data(self, new_merged_process_data):
        self.merged_process_data = new_merged_process_data

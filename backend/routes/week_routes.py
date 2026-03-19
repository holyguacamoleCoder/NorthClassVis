from flask import Blueprint, jsonify, request

from domain.features.calculators import FinalFeatureCalculator, PreliminaryFeatureCalculator
from services import week_service

class WeekRoutes:
    def __init__(self, config):
        self.config = config
        self.data_with_title_knowledge = self.config.get_submissions_with_knowledge_df()
        self.week_bp = Blueprint('week', __name__)
        self.register_routes()

    def register_routes(self):
        self.week_bp.add_url_rule('/week/week_data', view_func=self.week_analysis, methods=['GET'])
        self.week_bp.add_url_rule('/week/peak_data', view_func=self.peak_analysis, methods=['GET'])
    
    def update_data(self, new_config):
        self.config = new_config
        self.data_with_title_knowledge = self.config.get_submissions_with_knowledge_df()
        
    def week_analysis(self):
        student_ids = request.args.getlist('student_ids[]')

        df = self.data_with_title_knowledge.copy()
        if student_ids:
            df = df[df['student_ID'].isin(student_ids)]
        if df.empty:
            return jsonify({"students": []})

        start_date = df['time'].min()
        df['week'] = df['time'].apply(
            lambda value: week_service.calculate_week_of_year(value, start_date=start_date)
        )
        wr = self.config.get_week_range()
        df = week_service.filter_to_week_range(df, wr[0], wr[1]) if wr else week_service.filter_to_recent_weeks(df)
        if df.empty:
            return jsonify({"students": []})
        pre_calculator = PreliminaryFeatureCalculator(df)
        pre_calc_submit_records = pre_calculator.get_features()

        # 计算每个学生的总分，不区分知识点
        final_calculator = FinalFeatureCalculator(pre_calc_submit_records, ['student_ID', 'week', 'knowledge'])
        final_result = final_calculator.calc_final_features()

        result = final_result.to_dict(orient='index')
        result = week_service.week_scores_to_chart_payload(result)
        return jsonify(result)
    
    def peak_analysis(self):
        student_ids = request.args.getlist('student_ids[]')
        day = request.args.get('day', type=int)

        if day is None or not (1 <= day <= 7):
            return jsonify({"error": "Invalid day parameter. Must be between 1 and 7."}), 400

        df = self.data_with_title_knowledge
        if student_ids:
            df = df[df['student_ID'].isin(student_ids)]

        result_dict = week_service.calculate_peak_data(df, day)
        return jsonify(result_dict)
    
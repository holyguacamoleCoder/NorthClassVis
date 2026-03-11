from flask import Blueprint, jsonify, request

from services import question_service

class QuestionRoutes:
    def __init__(self, config):
        self.config = config
        self.data_with_title_knowledge = self.config.get_submissions_with_knowledge_df()
        self.question_bp = Blueprint('question', __name__)
        self.register_routes()

    def register_routes(self):
        self.question_bp.add_url_rule('/question/timeline/<title_id>', view_func=self.get_timeline_data, methods=['GET'])
        self.question_bp.add_url_rule('/question/distribution/<title_id>', view_func=self.get_distribution_data, methods=['GET'])
        self.question_bp.add_url_rule('/question/questions', view_func=self.get_question, methods=['GET'])

    def get_timeline_data(self, title_id):
        timeline_data = question_service.process_timeline_data(
            self.data_with_title_knowledge, title_id
        )
        return jsonify(timeline_data)

    def get_distribution_data(self, title_id):
        distribution_data = question_service.process_distribution_data(
            self.data_with_title_knowledge, title_id
        )
        return jsonify(distribution_data)

    def get_question(self):
        knowledge = request.args.get('knowledge', default=None, type=str)
        title_id = request.args.get('title_id', default=None, type=str)
        limit = request.args.get('limit', default=None, type=int)

        if title_id is not None:
            title_rows = self.data_with_title_knowledge[
                self.data_with_title_knowledge["title_ID"].astype(str) == str(title_id)
            ][["title_ID", "knowledge"]].drop_duplicates()
            if title_rows.empty:
                return jsonify({"error": "Title not found."}), 404

            title_row = title_rows.iloc[0]
            title_data = {
                "title_id": title_row["title_ID"],
                "knowledge": title_row["knowledge"],
                "timeline": question_service.process_timeline_data(
                    self.data_with_title_knowledge, title_id
                ),
                "distribution": question_service.process_distribution_data(
                    self.data_with_title_knowledge, title_id
                ),
                "avg_score": question_service.get_avg_score(
                    self.data_with_title_knowledge, title_id
                ),
                "sum_submit": question_service.get_sum_submit(
                    self.data_with_title_knowledge, title_id
                ),
            }
            return jsonify([title_data])
        elif knowledge is not None:
            titles_data = question_service.get_titles_data_by_knowledge(
                self.data_with_title_knowledge, knowledge, limit
            )
            return jsonify(titles_data)
        else:
            all_titles_data = question_service.get_all_titles_data(
                self.data_with_title_knowledge, limit
            )
            return jsonify(all_titles_data)
        
    def update_data(self, new_config):
        self.config = new_config
        self.data_with_title_knowledge = self.config.get_submissions_with_knowledge_df()
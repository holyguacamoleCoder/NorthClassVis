from flask import Blueprint, jsonify, request

from services import question_service


class QuestionRoutes:
    def __init__(self, config):
        self.config = config
        self.question_bp = Blueprint('question', __name__)
        self.register_routes()

    def register_routes(self):
        self.question_bp.add_url_rule('/question/timeline/<title_id>', view_func=self.get_timeline_data, methods=['GET'])
        self.question_bp.add_url_rule('/question/distribution/<title_id>', view_func=self.get_distribution_data, methods=['GET'])
        self.question_bp.add_url_rule('/question/questions', view_func=self.get_question, methods=['GET'])

    def get_timeline_data(self, title_id):
        data_with_title_knowledge = self.config.get_submissions_with_knowledge_df()
        timeline_data = question_service.process_timeline_data(
            data_with_title_knowledge, title_id
        )
        return jsonify(timeline_data)

    def get_distribution_data(self, title_id):
        data_with_title_knowledge = self.config.get_submissions_with_knowledge_df()
        distribution_data = question_service.process_distribution_data(
            data_with_title_knowledge, title_id
        )
        return jsonify(distribution_data)

    def get_question(self):
        data_with_title_knowledge = self.config.get_submissions_with_knowledge_df()
        knowledge = request.args.get('knowledge', default=None, type=str)
        title_id = request.args.get('title_id', default=None, type=str)
        limit = request.args.get('limit', default=None, type=int)

        if title_id is not None:
            title_data = question_service.get_title_data_by_id(
                data_with_title_knowledge,
                title_id,
            )
            if title_data is None:
                return self._error_response("Title not found.", "TITLE_NOT_FOUND", 404)
            return jsonify([title_data])
        elif knowledge is not None:
            titles_data = question_service.get_titles_data_by_knowledge(
                data_with_title_knowledge, knowledge, limit
            )
            return jsonify(titles_data)
        else:
            all_titles_data = question_service.get_all_titles_data(
                data_with_title_knowledge, limit
            )
            return jsonify(all_titles_data)

    def _error_response(self, message, code, status):
        return jsonify({"error": message, "code": code}), status
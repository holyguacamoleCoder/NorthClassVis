from flask import Blueprint, request, jsonify
from tools import QuestionView as qv

class QuestionRoutes:
    def __init__(self, config):
        self.config = config
        self.merged_process_data = self.config.get_merged_process_data()
        self.question_bp = Blueprint('question', __name__)
        self.register_routes()

    def register_routes(self):
        self.question_bp.add_url_rule('/question/timeline/<title_id>', view_func=self.get_timeline_data, methods=['GET'])
        self.question_bp.add_url_rule('/question/distribution/<title_id>', view_func=self.get_distribution_data, methods=['GET'])
        self.question_bp.add_url_rule('/question/questions', view_func=self.get_question, methods=['GET'])

    def get_timeline_data(self, title_id):
        timeline_data = qv.process_timeline_data(self.merged_process_data, title_id)
        return jsonify(timeline_data)

    def get_distribution_data(self, title_id):
        distribution_data = qv.process_distribution_data(self.merged_process_data, title_id)
        return jsonify(distribution_data)

    def get_question(self):
        knowledge = request.args.get('knowledge', default=None, type=str)
        title_id = request.args.get('title_id', default=None, type=int)
        limit = request.args.get('limit', default=None, type=int)

        if title_id is not None:
            # 如果指定了题目ID，则返回单个题目的数据
            title_data = {
                'title_id': title_id,
                'knowledge': self.merged_process_data.loc[self.merged_process_data['title_ID'] == title_id, 'knowledge'].iloc[0],
                'timeline': qv.process_timeline_data(self.merged_process_data, title_id),
                'distribution': qv.process_distribution_data(self.merged_process_data, title_id)
            }
            return jsonify([title_data])
        elif knowledge is not None:
            # 如果指定了知识点，则返回该知识点下所有题目的数据
            titles_data = qv.get_titles_data_by_knowledge(self.merged_process_data, knowledge, limit)
            return jsonify(titles_data)
        else:
            # 如果没有指定知识点或题目ID，则返回所有题目的数据
            all_titles_data = qv.get_all_titles_data(self.merged_process_data, limit)
            return jsonify(all_titles_data)
        
    def update_merged_process_data(self):
        self.merged_process_data = self.config.get_merged_process_data()
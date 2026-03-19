from flask import Blueprint, request, jsonify

from agent import Orchestrator


# LLM 配置（可选）：OPENAI_API_KEY、OPENAI_BASE_URL、OPENAI_MODEL；未设置时使用规则兜底生成 answer/actions


class AgentRoutes:
    def __init__(self, config, feature_factory=None):
        self.config = config
        self.feature_factory = feature_factory
        self.orchestrator = Orchestrator(config, feature_factory)
        self.agent_bp = Blueprint("agent", __name__)
        self.register_routes()

    def register_routes(self):
        self.agent_bp.add_url_rule("/agent/query", view_func=self.post_query, methods=["POST"])
        self.agent_bp.add_url_rule("/meta/knowledge_points", view_func=self.get_knowledge_points, methods=["GET"])

    def get_knowledge_points(self):
        q = request.args.get("q", default="", type=str).strip()
        df = self.config.get_submissions_with_knowledge_df()
        if df is None or "knowledge" not in df.columns:
            return jsonify([])
        points = df["knowledge"].dropna().unique().tolist()
        points = [str(p).strip() for p in points if str(p).strip()]
        if q:
            points = [p for p in points if q in p]
        return jsonify(points)

    def post_query(self):
        body = request.get_json(silent=True) or {}
        question = body.get("question")
        context = body.get("context") or {}
        if not question:
            return jsonify({
                "answer": "请提供 question 参数。",
                "evidence": [],
                "actions": [],
                "visual_links": [],
                "trace": {"steps": []},
            }), 400
        result = self.orchestrator.query(question, context)
        # 前端约定：顶层直接返回 answer/evidence/actions/visual_links/trace，不包 data
        return jsonify(result)

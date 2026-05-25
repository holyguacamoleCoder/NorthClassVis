from flask import Blueprint, jsonify, request

from agent.http_service import AgentHttpService


class AgentRoutes:
    def __init__(self, config, feature_factory=None):
        self.config = config
        self.feature_factory = feature_factory
        self.service = AgentHttpService.get()
        self.agent_bp = Blueprint("agent", __name__)
        self.register_routes()

    def register_routes(self):
        self.agent_bp.add_url_rule("/agent/query", view_func=self.post_query, methods=["POST"])
        self.agent_bp.add_url_rule("/agent/sessions", view_func=self.list_sessions, methods=["GET"])
        self.agent_bp.add_url_rule("/agent/sessions", view_func=self.create_session, methods=["POST"])
        self.agent_bp.add_url_rule(
            "/agent/sessions/<session_id>",
            view_func=self.get_session,
            methods=["GET"],
        )
        self.agent_bp.add_url_rule(
            "/agent/sessions/<session_id>",
            view_func=self.patch_session,
            methods=["PATCH"],
        )
        self.agent_bp.add_url_rule(
            "/agent/sessions/<session_id>",
            view_func=self.delete_session,
            methods=["DELETE"],
        )
        self.agent_bp.add_url_rule(
            "/agent/sessions/<session_id>/activate",
            view_func=self.activate_session,
            methods=["POST"],
        )
        self.agent_bp.add_url_rule(
            "/agent/sessions/<session_id>/messages",
            view_func=self.post_message,
            methods=["POST"],
        )
        self.agent_bp.add_url_rule(
            "/agent/jobs/<job_id>",
            view_func=self.get_job,
            methods=["GET"],
        )
        self.agent_bp.add_url_rule(
            "/agent/approvals/<approval_id>",
            view_func=self.post_approval,
            methods=["POST"],
        )
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
        try:
            result = self.service.query_legacy(str(question), context)
            return jsonify(result)
        except Exception as exc:
            return jsonify({
                "answer": f"Agent 执行失败：{exc}",
                "evidence": [],
                "actions": [],
                "visual_links": [],
                "trace": {"steps": []},
            }), 500

    def list_sessions(self):
        return jsonify({
            "sessions": self.service.list_sessions(),
            "active_session_id": self.service.get_active_session_id(),
        })

    def create_session(self):
        body = request.get_json(silent=True) or {}
        session = self.service.create_session(
            permission_mode=str(body.get("permission_mode") or "analyze"),
            title=body.get("title"),
        )
        return jsonify(session), 201

    def get_session(self, session_id: str):
        session = self.service.get_session(session_id)
        if session is None:
            return jsonify({"error": "session not found"}), 404
        return jsonify(session)

    def patch_session(self, session_id: str):
        body = request.get_json(silent=True) or {}
        session = self.service.update_session(session_id, body)
        if session is None:
            return jsonify({"error": "session not found"}), 404
        return jsonify(session)

    def delete_session(self, session_id: str):
        if not self.service.delete_session(session_id):
            return jsonify({"error": "session not found"}), 404
        return jsonify({"ok": True})

    def activate_session(self, session_id: str):
        session = self.service.switch_session(session_id)
        if session is None:
            return jsonify({"error": "session not found"}), 404
        return jsonify(session)

    def post_message(self, session_id: str):
        body = request.get_json(silent=True) or {}
        content = body.get("content") or body.get("question")
        context = body.get("context") or {}
        try:
            payload = self.service.submit_message(
                session_id,
                content=str(content or ""),
                context=context,
            )
            return jsonify(payload), 202
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

    def get_job(self, job_id: str):
        job = self.service.get_job(job_id)
        if job is None:
            return jsonify({"error": "job not found"}), 404
        return jsonify(job)

    def post_approval(self, approval_id: str):
        body = request.get_json(silent=True) or {}
        decision = body.get("decision") or "deny"
        remember = bool(body.get("remember"))
        if not self.service.resolve_approval(approval_id, decision=decision, remember=remember):
            return jsonify({"error": "approval not found or already resolved"}), 404
        return jsonify({"ok": True})

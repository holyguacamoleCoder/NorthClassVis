"""
手工调试意图解析（LLM 主路径 + 规则兜底）。

用法（在项目根目录）：
    cd backend
    ..\\.venv\\Scripts\\python.exe test_intent_llm.py

确保：
- 设置 OPENAI_API_KEY / OPENAI_BASE_URL / OPENAI_MODEL 后，可验证 LLM 主路径行为
- 不设置 OPENAI_API_KEY 时，可验证规则兜底路径不会报错
"""

import os
import sys


def _ensure_backend_on_path():
    backend = os.path.dirname(os.path.abspath(__file__))
    if backend not in sys.path:
        sys.path.insert(0, backend)


def main():
    _ensure_backend_on_path()

    from agent.common.context_utils import normalize_context
    from agent.common.llm_client import get_default_llm_client
    from agent.intent import parse_intent

    client = get_default_llm_client()
    cfg = client.config
    print("LLMConfig: api_key_set=%s base_url=%s model=%s" % (bool(cfg.api_key), cfg.base_url, cfg.model))
    print("LLM available:", cfg.is_available())
    print("-" * 80)

    samples = [
        "链表知识点大家掌握得如何？",
        "最近两周学生状况如何？",
        "班里的学生分层是什么情况？",
        "学生心情不好怎么办？",
        "帮我看看这个学生最近学得怎么样",
    ]

    # 模拟一个带 classes/majors 的上下文，用于 scope 推导
    context = {"classes": ["Part"], "majors": ["All"], "selected_student_ids": []}
    ctx_norm = normalize_context(context)
    print("Normalized context:", ctx_norm)
    print("-" * 80)

    for q in samples:
        print("Q:", q)
        intent = parse_intent(q, ctx_norm)
        d = intent.to_dict()
        print("  intent_type:", d.get("intent_type"))
        print("  subject   :", d.get("subject"))
        print("  mode      :", d.get("mode"))
        print("  scope     :", d.get("scope"))
        print("  knowledge :", d.get("knowledge"))
        print("  title_id  :", d.get("title_id"))
        print("  student_ids:", d.get("student_ids"))
        print("  is_out_of_domain:", d.get("is_out_of_domain"))
        print("  needs_clarification:", d.get("needs_clarification"))
        if d.get("clarification_question"):
            print("  clarification_question:", d.get("clarification_question"))
        print("-" * 80)


if __name__ == "__main__":
    main()


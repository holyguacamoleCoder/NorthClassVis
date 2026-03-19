import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except Exception:
    def load_dotenv(*args, **kwargs):
        return False

# 从 app.py 同目录加载 .env，使 OPENAI_API_KEY 等变量在 os.environ 中可用
_env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(_env_path)

from flask import Flask
from flask_cors import CORS
# from flask_limiter import Limiter
# from flask_limiter.util import get_remote_address
from routes import api_bp

app = Flask(__name__)
# 使用 Flask-Cors 自动处理 CORS 头部
CORS(app) 

# 配置Flask-Limiter
# limiter = Limiter(
#     app=app,
#     key_func=get_remote_address,
#     default_limits=["10 per minute"]
# )

# 注册蓝图
app.register_blueprint(api_bp)


def _check_openai_env():
    """启动时检查 OpenAI 相关环境变量是否可用（不输出敏感内容）。"""
    key = os.environ.get("OPENAI_API_KEY")
    if key and key.strip() and not key.startswith("your_"):
        app.logger.info("LLM 配置已加载（OPENAI_API_KEY 已设置），Agent 将使用 LLM 生成回答。")
    else:
        app.logger.info("未设置有效的 OPENAI_API_KEY，Agent 将使用规则兜底生成回答。")


if __name__ == '__main__':
    with app.app_context():
        _check_openai_env()
    app.run(debug=True)


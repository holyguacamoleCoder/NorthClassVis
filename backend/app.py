from flask import Flask
from flask_cors import CORS
# from flask_limiter import Limiter
# from flask_limiter.util import get_remote_address
from routes.main_routes import api_bp

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

if __name__ == '__main__':
    app.run(debug=True)


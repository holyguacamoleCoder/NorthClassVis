# NorthClassVision 单镜像部署：前端 + 后端 + Nginx
# 构建：在项目根目录执行  docker build -f deploy/Dockerfile -t northclassvision:latest .
# 运行：docker run -p 8080:80 northclassvision:latest

# ---------- Stage 1: 构建前端 ----------
FROM node:20-alpine AS frontend-builder

WORKDIR /build

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ .
# 生产构建使用相对路径 /api，由容器内 Nginx 反代
ENV VUE_APP_API_BASE_URL=/api
RUN npm run build

# ---------- Stage 2: 运行镜像 ----------
FROM python:3.11-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends nginx \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 后端依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

# 后端代码与数据（数据目录需存在，或运行时用 -v 挂载）
COPY backend ./backend
COPY data ./data

# 前端构建产物
COPY --from=frontend-builder /build/dist ./frontend/dist

# Nginx 配置与启动脚本
COPY deploy/nginx.docker.conf /etc/nginx/conf.d/default.conf
COPY deploy/start.sh /start.sh
RUN chmod +x /start.sh

EXPOSE 80

CMD ["/start.sh"]

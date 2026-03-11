#!/bin/sh
set -e
# 后端：gunicorn 监听本机 5000，供 Nginx 反代
cd /app/backend && gunicorn -w 4 -b 127.0.0.1:5000 --timeout 120 app:app &
# 前台运行 Nginx
exec nginx -g "daemon off;"

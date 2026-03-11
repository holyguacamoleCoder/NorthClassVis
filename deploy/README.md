# 部署说明

## Docker 单镜像部署（推荐）

前端、后端、Nginx 打成一个镜像，一次构建到处运行。

**前提**：项目根目录下存在 `data/` 目录且内含所需数据（如 `Data_SubmitRecord/`、`Data_TitleInfo.csv`、`Data_StudentInfo.csv`）。若数据未纳入仓库，可在运行容器时挂载：`-v /宿主机/data:/app/data`。

**构建**（在项目根目录执行）：

```bash
docker build -f deploy/Dockerfile -t northclassvision:latest .
```

**运行**：

```bash
docker run -p 8080:80 northclassvision:latest
```

浏览器访问 `http://localhost:8080`。若需挂载数据目录：

```bash
docker run -p 8080:80 -v /path/to/your/data:/app/data northclassvision:latest
```

---

## Nginx 生产部署（非 Docker）

1. 构建前端：在 `frontend/` 下执行 `npm run build`，得到 `frontend/dist/`。
2. 将 `frontend/dist/` 内容放到服务器目录，例如 `/var/www/northclassvision/dist`。
3. 修改 `nginx.conf`：
   - `server_name` 改为你的域名或保留 `localhost`。
   - `root` 改为上一步的前端静态目录，如 `root /var/www/northclassvision/dist;`。
   - 若后端不在本机或端口不是 5000，修改 `upstream backend` 的 `server`，如 `server 你的后端IP:端口;`。
4. 将 `nginx.conf` 中 `server { ... }` 和 `upstream backend { ... }` 拷入站点配置（如 `/etc/nginx/conf.d/northclassvision.conf`），或整体 include。
5. 执行 `nginx -t` 校验配置，再 `nginx -s reload` 重载。

后端需单独运行（如 `python backend/app.py` 或 gunicorn/uwsgi），并保证 Nginx 中 `upstream backend` 的地址与后端监听一致。

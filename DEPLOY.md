# 部署指南

这个项目目前适合先部署成 Demo/内测版：单进程 Python 服务 + SQLite + 本地上传目录 + Nginx 反向代理。

上线前建议先去 MiniMax / DeepSeek 后台重新生成新的 API Key，并废弃聊天里出现过的旧 Key。线上不要把真实 Key 写进源码。

## 方案 A：宝塔 + Docker（推荐，edu.ms1001.com）

适合已有宝塔面板的服务器，当前项目已内置完整配置。

### 1. 上传代码

把整个项目放到 `/www/wwwroot/edu.ms1001.com`。

### 2. 一键安装

```bash
cd /www/wwwroot/edu.ms1001.com
chmod +x deploy/install.sh
bash deploy/install.sh
```

### 3. 配置环境变量

```bash
nano .env
```

必填：

- `MINIMAX_API_KEY` — OCR 和拆题
- `ADMIN_EMAIL` / `ADMIN_PASSWORD` — 管理员账号（首次启动自动创建；历史记录归属该账号）

可选：`DEEPSEEK_API_KEY`、`OPENAI_API_KEY`、`FENNO_API_KEY`

改完后重启：

```bash
docker compose restart
```

### 4. 配置宝塔 Nginx

将 `deploy/nginx/edu.ms1001.com.conf` 的内容**完整替换**到宝塔站点配置中：

> 网站 → edu.ms1001.com → 设置 → 配置文件

**注意**：后端端口是 **8020**（不是 8010/8000）。旧版「AI平面设计系统」配置不能直接复用。

或直接复制：

```bash
cp deploy/nginx/edu.ms1001.com.conf /www/server/panel/vhost/nginx/edu.ms1001.com.conf
nginx -t && nginx -s reload
```

### 5. 验证

```bash
curl http://127.0.0.1:8020/healthz
curl -I https://edu.ms1001.com
```

浏览器打开 `https://edu.ms1001.com`，使用 `.env` 中的 `ADMIN_EMAIL` / `ADMIN_PASSWORD` 登录管理员账号，即可查看全部历史记录并进入「后台配置」。

## 方案 B：Docker Compose（通用 Linux）

适合先跑 Demo。

### 1. 准备服务器

推荐起步配置：

- 2 核 4G：少量内测
- 4 核 8G：更稳妥
- 磁盘至少 40G，图片上传多的话更大

服务器安装 Docker 和 Docker Compose。

### 2. 上传代码

把整个项目放到服务器，例如：

```bash
sudo mkdir -p /opt/gaokao-ai
sudo chown -R "$USER":"$USER" /opt/gaokao-ai
cd /opt/gaokao-ai
```

上传项目文件后：

```bash
cp .env.example .env
nano .env
```

填入真实的 `MINIMAX_API_KEY`、`DEEPSEEK_API_KEY`。如果要生成错题学习卡片，还需要配置 `OPENAI_API_KEY`；图片模型可用 `OPENAI_IMAGE_MODEL` 覆盖，也可以在后台“图片模型配置”中修改。
如果使用 Fenno 这类 OpenAI 兼容中转，也可以配置 `FENNO_API_KEY`，然后在后台填 Base URL `https://api.fenno.ai`；系统会自动拼接聊天和图片接口。

### 3. 启动

```bash
docker compose up -d --build
docker compose logs -f
```

检查：

```bash
curl http://127.0.0.1:8020/healthz
```

### 4. 配 Nginx

先用 HTTP 模板：

```bash
sudo cp deploy/nginx/gaokao.http.conf /etc/nginx/sites-available/gaokao-ai
sudo nano /etc/nginx/sites-available/gaokao-ai
```

把 `example.com` 改成你的域名。

```bash
sudo ln -s /etc/nginx/sites-available/gaokao-ai /etc/nginx/sites-enabled/gaokao-ai
sudo nginx -t
sudo systemctl reload nginx
```

域名解析生效后，用 Certbot 签 HTTPS，再把配置切到 `deploy/nginx/gaokao.https.conf`。

## 方案 C：systemd 原生部署

适合不用 Docker 的服务器。

### 1. 安装依赖

```bash
sudo apt update
sudo apt install -y python3 python3-venv nginx
```

### 2. 创建用户和目录

```bash
sudo useradd --system --create-home --shell /usr/sbin/nologin gaokao
sudo mkdir -p /opt/gaokao-ai /etc/gaokao-ai
sudo chown -R gaokao:gaokao /opt/gaokao-ai
```

上传项目到 `/opt/gaokao-ai`。

### 3. 环境变量

```bash
sudo cp /opt/gaokao-ai/deploy/env.production.example /etc/gaokao-ai/gaokao.env
sudo nano /etc/gaokao-ai/gaokao.env
sudo chmod 600 /etc/gaokao-ai/gaokao.env
sudo chown root:root /etc/gaokao-ai/gaokao.env
```

### 4. 安装 systemd 服务

```bash
sudo cp /opt/gaokao-ai/deploy/systemd/gaokao-ai.service /etc/systemd/system/gaokao-ai.service
sudo systemctl daemon-reload
sudo systemctl enable --now gaokao-ai
sudo systemctl status gaokao-ai
```

检查：

```bash
curl http://127.0.0.1:8020/healthz
```

### 5. 配 Nginx

和 Docker 方案相同，使用 `deploy/nginx/gaokao.http.conf` 或 HTTPS 模板。

## 备份

SQLite、上传图片和生成的学习卡片都必须备份。

```bash
sudo mkdir -p /var/backups/gaokao-ai
sudo bash /opt/gaokao-ai/deploy/scripts/backup.sh
```

加入每日定时任务：

```bash
sudo crontab -e
```

加入：

```cron
15 3 * * * APP_DIR=/opt/gaokao-ai BACKUP_DIR=/var/backups/gaokao-ai bash /opt/gaokao-ai/deploy/scripts/backup.sh >/var/log/gaokao-ai-backup.log 2>&1
```

恢复：

```bash
sudo systemctl stop gaokao-ai
sudo APP_DIR=/opt/gaokao-ai bash /opt/gaokao-ai/deploy/scripts/restore.sh /var/backups/gaokao-ai/gaokao-ai-YYYYmmdd-HHMMSS.tar.gz
sudo systemctl start gaokao-ai
```

## 生产注意事项

- 当前版本是内测架构，不要直接开放给大量用户。
- `data/gaokao.db` 里会保存模型配置和 API Key，服务器权限必须收紧。
- `web/uploads/` 会保存用户上传图片，`web/cards/` 会保存 GPT Image 生成的错题卡片，必须定期清理或迁移对象存储。
- Nginx `client_max_body_size` 当前是 25m，可按图片大小调整。
- LLM 请求较慢，Nginx 超时已配置为 180 秒。
- 多用户正式版应升级：登录、用户隔离、PostgreSQL、对象存储、任务队列、审计日志。

## 常用命令

Docker：

```bash
docker compose ps
docker compose logs -f
docker compose restart
```

systemd：

```bash
sudo systemctl status gaokao-ai
sudo journalctl -u gaokao-ai -f
sudo systemctl restart gaokao-ai
```

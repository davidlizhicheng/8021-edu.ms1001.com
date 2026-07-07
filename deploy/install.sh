#!/usr/bin/env bash
# Gaokao AI — 一键安装/更新（宝塔 / 通用 Linux）
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$APP_DIR"

echo "========================================"
echo " Gaokao AI 安装脚本"
echo " 目录: $APP_DIR"
echo "========================================"

if ! command -v docker >/dev/null 2>&1; then
  echo "错误: 未找到 docker，请先安装 Docker。"
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "错误: 未找到 docker compose，请先安装 Docker Compose 插件。"
  exit 1
fi

mkdir -p data web/uploads web/cards

if [ ! -f .env ]; then
  cp .env.example .env
  echo "已创建 .env，请编辑后重新运行本脚本或直接 docker compose up -d --build"
fi

# 确保持久化目录可写
chmod 755 data web/uploads web/cards 2>/dev/null || true

echo ""
echo ">>> 构建并启动容器..."
docker compose up -d --build

echo ""
echo ">>> 等待服务就绪..."
for i in $(seq 1 15); do
  if curl -sf http://127.0.0.1:8020/healthz >/dev/null 2>&1; then
    echo "健康检查通过: http://127.0.0.1:8020/healthz"
    break
  fi
  sleep 2
  if [ "$i" -eq 15 ]; then
    echo "警告: 健康检查超时，请执行 docker compose logs -f 查看日志"
    exit 1
  fi
done

echo ""
echo "========================================"
echo " 安装完成"
echo "========================================"
echo ""
echo "本地服务: http://127.0.0.1:8020"
echo ""
echo "下一步（宝塔站点 edu.ms1001.com）:"
echo "  1. 编辑 .env，填入 MINIMAX_API_KEY 和 ADMIN_EMAIL / ADMIN_PASSWORD"
echo "  2. 将 deploy/nginx/edu.ms1001.com.conf 内容复制到宝塔站点 Nginx 配置"
echo "     （或: sudo cp deploy/nginx/edu.ms1001.com.conf /www/server/panel/vhost/nginx/edu.ms1001.com.conf）"
echo "  3. 宝塔 → 网站 → edu.ms1001.com → 重载 Nginx"
echo "  4. 浏览器访问 https://edu.ms1001.com"
echo ""
echo "常用命令:"
echo "  docker compose logs -f"
echo "  docker compose restart"
echo "  bash deploy/scripts/backup.sh"

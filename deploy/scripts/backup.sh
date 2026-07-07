#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/gaokao-ai}"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/gaokao-ai}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"

timestamp="$(date +%Y%m%d-%H%M%S)"
target="${BACKUP_DIR}/gaokao-ai-${timestamp}.tar.gz"

mkdir -p "${BACKUP_DIR}"
mkdir -p "${APP_DIR}/web/uploads" "${APP_DIR}/web/cards"

tar -czf "${target}" \
  -C "${APP_DIR}" \
  data/gaokao.db \
  web/uploads \
  web/cards

find "${BACKUP_DIR}" -name "gaokao-ai-*.tar.gz" -mtime "+${RETENTION_DAYS}" -delete

echo "backup written: ${target}"

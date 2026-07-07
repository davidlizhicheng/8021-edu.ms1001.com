#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/gaokao-ai}"

if [[ $# -ne 1 ]]; then
  echo "usage: $0 /path/to/gaokao-ai-YYYYmmdd-HHMMSS.tar.gz" >&2
  exit 1
fi

backup="$1"
if [[ ! -f "${backup}" ]]; then
  echo "backup not found: ${backup}" >&2
  exit 1
fi

echo "Stop the service before restore:"
echo "  sudo systemctl stop gaokao-ai"
echo
read -r -p "Restore ${backup} into ${APP_DIR}? This overwrites data and uploads. Type YES: " confirm
if [[ "${confirm}" != "YES" ]]; then
  echo "restore cancelled"
  exit 1
fi

tar -xzf "${backup}" -C "${APP_DIR}"
echo "restore complete"

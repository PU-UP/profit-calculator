#!/usr/bin/env bash
# 交易小算盘 Streamlit 启动脚本（默认端口 8001）
# 用法: ./scripts/start.sh
#       ./scripts/start.sh 9000
#       PORT=9000 ./scripts/start.sh

set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PORT="${1:-${PORT:-8001}}"
echo "启动 Streamlit: http://localhost:${PORT}"
if [ "${PORT}" = "8001" ]; then
  exec uv run start
fi
exec uv run start "${PORT}"

#!/usr/bin/env bash
# 交易小算盘 NiceGUI 启动脚本（默认端口 8001）
# 用法: ./scripts/start-nicegui.sh
#       ./scripts/start-nicegui.sh 9000
#       PORT=9000 ./scripts/start-nicegui.sh

set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PORT="${1:-${PORT:-8001}}"
echo "启动 NiceGUI: http://localhost:${PORT}"
if [ "$PORT" = "8001" ]; then
  uv run start-nicegui
else
  uv run start-nicegui "$PORT"
fi

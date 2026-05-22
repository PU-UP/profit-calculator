#!/usr/bin/env bash
# 交易小算盘 一键部署脚本
# 用法：bash deploy.sh [安装目录]
set -euo pipefail

INSTALL_DIR="${1:-/opt/profit-calculator}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "🥗 交易小算盘 部署脚本"
echo "   安装目录: ${INSTALL_DIR}"
echo ""

# 1. 创建目录
echo "[1/5] 创建目录..."
sudo mkdir -p "${INSTALL_DIR}"
sudo mkdir -p "${INSTALL_DIR}/static"

# 2. 复制文件
echo "[2/5] 复制文件..."
sudo cp -r "${SCRIPT_DIR}/profit_calc" "${INSTALL_DIR}/"
sudo cp "${SCRIPT_DIR}/nicegui_app.py" "${INSTALL_DIR}/"
sudo cp "${SCRIPT_DIR}/requirements.txt" "${INSTALL_DIR}/"
sudo cp "${SCRIPT_DIR}/.env.example" "${INSTALL_DIR}/.env.example"

# 如果已有 .env 则不覆盖
if [ ! -f "${INSTALL_DIR}/.env" ]; then
    sudo cp "${INSTALL_DIR}/.env.example" "${INSTALL_DIR}/.env"
    echo "   ⚠ 已创建 .env，请编辑填写 MINIMAX_API_KEY"
else
    echo "   ✓ .env 已存在，跳过"
fi

# 3. 创建虚拟环境 & 安装依赖
echo "[3/5] 安装 Python 依赖..."
if [ ! -d "${INSTALL_DIR}/venv" ]; then
    sudo python3 -m venv "${INSTALL_DIR}/venv"
fi
sudo "${INSTALL_DIR}/venv/bin/pip" install --upgrade pip --quiet
sudo "${INSTALL_DIR}/venv/bin/pip" install -r "${INSTALL_DIR}/requirements.txt" --quiet

# 4. 设置权限
echo "[4/5] 设置权限..."
sudo chown -R www-data:www-data "${INSTALL_DIR}"
sudo chmod 600 "${INSTALL_DIR}/.env"

# 5. 安装 systemd 服务
echo "[5/5] 安装 systemd 服务..."
sudo cp "${SCRIPT_DIR}/profit-calculator.service" /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable profit-calculator
sudo systemctl restart profit-calculator

echo ""
echo "✅ 部署完成！"
echo ""
echo "下一步："
echo "  1. 编辑 .env 填写 MINIMAX_API_KEY："
echo "     sudo nano ${INSTALL_DIR}/.env"
echo "  2. 重启服务："
echo "     sudo systemctl restart profit-calculator"
echo "  3. 查看状态："
echo "     sudo systemctl status profit-calculator"
echo "  4. 访问：http://localhost:8001"
echo "  5. iPhone Safari → 分享 → 添加到主屏幕 🧮"
echo ""
echo "可选：配置 Nginx 反向代理 + HTTPS"
echo "  参考配置见下方注释："
echo ""
cat << 'NGINX'
# /etc/nginx/sites-available/profit-calculator
# server {
#     listen 443 ssl http2;
#     server_name calc.yourdomain.com;
#
#     ssl_certificate /etc/letsencrypt/live/calc.yourdomain.com/fullchain.pem;
#     ssl_certificate_key /etc/letsencrypt/live/calc.yourdomain.com/privkey.pem;
#
#     location / {
#         proxy_pass http://127.0.0.1:8001;
#         proxy_http_version 1.1;
#         proxy_set_header Upgrade $http_upgrade;
#         proxy_set_header Connection "upgrade";
#         proxy_set_header Host $host;
#         proxy_set_header X-Real-IP $remote_addr;
#         proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
#         proxy_set_header X-Forwarded-Proto $scheme;
#         proxy_read_timeout 86400;
#     }
# }
NGINX

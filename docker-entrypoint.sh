#!/bin/bash
set -e

# 配置 SSH 密钥环境
SSH_DIR="/home/vmcontrolhub/.ssh"
KEY_FILE="$SSH_DIR/id_rsa"

# 修复 .ssh 目录权限
chown -R 2000:2000 "$SSH_DIR"
chmod 700 "$SSH_DIR"

# 首次启动自动生成 SSH 密钥
if [ ! -f "$KEY_FILE" ]; then
    echo "==> Environment initialization detected: generating SSH key..."
    ssh-keygen -t rsa -b 3072 -N "" -f "$KEY_FILE" -q
fi

# 强制密钥安全权限
chmod 600 "$KEY_FILE"

echo "==> Environment ready, starting VM Control Hub..."

# 启动 VM Control Hub 应用
exec gunicorn -c gunicorn_config.py run:app
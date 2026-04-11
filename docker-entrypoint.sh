#!/bin/bash
set -e

# 配置 SSH 密钥环境
SSH_DIR="/home/vmcontrolhub/.ssh"
KEY_FILE="$SSH_DIR/id_rsa"

if [ -f "$KEY_FILE" ]; then
    echo "==> SSH key file detected, skipping generation."
else
    echo "==> Environment initialization detected: generating SSH key..."
    ssh-keygen -t rsa -b 3072 -N "" -f "$KEY_FILE" -q
fi

chown -R 2000:2000 "$SSH_DIR"
chmod 700 "$SSH_DIR"
chmod 600 "$KEY_FILE"

# 启动应用
exec gunicorn -c gunicorn_config.py run:app
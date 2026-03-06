#!/bin/bash
set -e

SSH_DIR="/home/vmcontrolhub/.ssh"
KEY_FILE="$SSH_DIR/id_rsa"
SOCK_FILE="$SSH_DIR/ssh-agent.sock"
chown -R 2000:2000 "$SSH_DIR"
chmod 700 "$SSH_DIR"

# 1. 检查并生成 SSH 密钥
if [ ! -f "$KEY_FILE" ]; then
    echo "==> 检测到环境初始化：生成 SSH 密钥..."
    ssh-keygen -t rsa -b 3072 -N "" -f "$KEY_FILE"
fi

# 2. 强制权限修复
chmod 600 "$KEY_FILE"

# 3. 启动 ssh-agent 并加载密钥
if [ -S "$SOCK_FILE" ]; then rm -f "$SOCK_FILE"; fi

# 这里启动 Agent
eval "$(ssh-agent -s -a "$SOCK_FILE")"
ssh-add "$KEY_FILE"

echo "==> 环境准备就绪，启动应用..."
exec "$@"
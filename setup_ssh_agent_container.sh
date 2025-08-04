#!/bin/bash

set -e

# 1. 创建 vmcontrolhub 用户和组
echo "==> 创建用户和组: vmcontrolhub (UID/GID 2000)"
groupadd -g 2000 vmcontrolhub || echo "Group already exists"
useradd -m -u 2000 -g 2000 -s /bin/bash vmcontrolhub || echo "User already exists"

# 2. 切换到 vmcontrolhub 生成 SSH 密钥
echo "==> 为 vmcontrolhub 生成 SSH 密钥"
sudo -u vmcontrolhub bash <<'EOF'
set -e
mkdir -p ~/.ssh
chmod 700 ~/.ssh
if [ ! -f ~/.ssh/id_rsa ]; then
    ssh-keygen -t rsa -N "" -f ~/.ssh/id_rsa
fi

cp ~/.ssh/id_rsa ~/.ssh/id_rsa_container
chmod 600 ~/.ssh/id_rsa_container

# 测试无口令加载
eval "$(ssh-agent -s)"
ssh-add ~/.ssh/id_rsa_container
ssh-add -l
ssh-agent -k
EOF

# 3. 创建 systemd 服务单元
echo "==> 创建 systemd 服务单元 /etc/systemd/system/ssh-agent-container.service"
cat <<EOF | sudo tee /etc/systemd/system/ssh-agent-container.service > /dev/null
[Unit]
Description=System-wide SSH Agent for Containers
After=network.target

[Service]
Type=simple
User=vmcontrolhub
Environment=SSH_AUTH_SOCK=/home/vmcontrolhub/.ssh/ssh-agent.sock
ExecStart=/usr/bin/ssh-agent -D -a /home/vmcontrolhub/.ssh/ssh-agent.sock
ExecStartPost=/usr/bin/ssh-add /home/vmcontrolhub/.ssh/id_rsa_container
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF

# 4. 启用并启动服务
echo "==> 启用并启动 ssh-agent-container 服务"
sudo systemctl daemon-reload
sudo systemctl enable ssh-agent-container.service
sudo systemctl start ssh-agent-container.service
sudo systemctl status ssh-agent-container.service --no-pager
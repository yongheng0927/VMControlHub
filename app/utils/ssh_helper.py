# app/utils/ssh_helper.py

import os
import paramiko
from flask import current_app
from paramiko import RSAKey


def get_ssh_user():
    """
    获取 SSH 用户名
    
    优先级：
    1. SSH_USER 环境变量
    2. VM_SSH_USER 环境变量（备选）
    
    :return: SSH 用户名
    """
    ssh_user = os.getenv('SSH_USER')
    return ssh_user


def get_ssh_key_file():
    """
    获取 SSH 私钥文件路径
    
    :return: SSH 私钥文件路径
    :raises ValueError: 如果 SSH_KEY_FILE 环境变量未设置
    """
    ssh_key_file = os.getenv('SSH_KEY_FILE')
    if not ssh_key_file:
        raise ValueError("SSH_KEY_FILE environment variable is not set")
    return ssh_key_file


def execute_ssh_command(host, command, ssh_user=None, timeout=30):
    """
    执行 SSH 命令
    
    :param host: 宿主机 IP
    :param command: 要执行的命令
    :param ssh_user: SSH 用户名（可选，如果不传则从环境变量获取）
    :param timeout: 超时时间（秒，默认 30）
    :return: (output, error, exit_status)
    """
    if ssh_user is None:
        ssh_user = get_ssh_user()
    
    if not ssh_user:
        raise ValueError("SSH user not configured")
    
    ssh_key_file = get_ssh_key_file()
    
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        private_key = RSAKey.from_private_key_file(ssh_key_file)
        client.connect(
            hostname=host,
            username=ssh_user,
            pkey=private_key,
            timeout=timeout,
            banner_timeout=timeout,
            auth_timeout=timeout,
            allow_agent=False,
            look_for_keys=False
        )
        stdin, stdout, stderr = client.exec_command(command)
        exit_status = stdout.channel.recv_exit_status()
        output = stdout.read().decode('utf-8').strip()
        error = stderr.read().decode('utf-8').strip()
        
        return output, error, exit_status
        
    except Exception as e:
        current_app.logger.error(f"SSH connection failed: host={host}, username={ssh_user}, error={str(e)}")
        return None, str(e), -1
    
    finally:
        if client.get_transport() and client.get_transport().is_active():
            client.close()
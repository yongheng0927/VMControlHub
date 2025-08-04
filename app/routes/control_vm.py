from flask import Blueprint, render_template, request, jsonify, current_app
from flask_login import login_required, current_user
from sqlalchemy.orm import joinedload
from app.models import db, VM, OperationLog
import os
import re
import paramiko
from datetime import datetime

control_vm_bp = Blueprint('control_vm', __name__, url_prefix='/')

# ------------------------------
# 核心工具函数
# ------------------------------
def execute_ssh_command(host, username, command):
    """执行SSH命令,返回(输出, 错误, 退出码)"""
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(hostname=host, username=username, timeout=10)
        stdin, stdout, stderr = client.exec_command(command)
        exit_status = stdout.channel.recv_exit_status()
        output = stdout.read().decode('utf-8').strip()
        error = stderr.read().decode('utf-8').strip()
        return output, error, exit_status
    
    except Exception as e:
        current_app.logger.error(f"SSH connection failed: host={host}, username={username}, error={str(e)}")
        return None, str(e), -1
    
    finally:
        if client.get_transport() and client.get_transport().is_active():
            client.close()


def get_vm_identifier_cached(host_type, host_ip, ssh_user, vm_ip, cache={}):
    """获取VM标识并缓存结果"""
    cache_key = f"{host_type}_{host_ip}_{vm_ip}"
    if cache_key in cache:
        return cache[cache_key]
    
    # 首次获取并缓存
    if host_type == 'pve':
        output, err, _ = execute_ssh_command(host_ip, ssh_user, "sudo qm list")
        if err:
            cache[cache_key] = (None, f"Failed to get PVE list: {err}")
        else:
            vmid = None
            for line in output.split('\n'):
                if re.search(r'\b' + re.escape(vm_ip) + r'\b', line):
                    vmid = line.strip().split()[0]
                    break
            cache[cache_key] = (vmid, f"PVE VM with IP {vm_ip} not found" if not vmid else None)
    
    elif host_type == 'kvm':
        output, err, _ = execute_ssh_command(host_ip, ssh_user, "sudo virsh list --all --name")
        if err:
            cache[cache_key] = (None, f"Failed to get KVM list: {err}")
            return cache[cache_key]
        
        target_vm_name = None
        ip_pattern = re.escape(vm_ip) + r'-'
        for vm_name in output.strip().split('\n'):
            if vm_name.strip() and re.match(ip_pattern, vm_name.strip()):
                target_vm_name = vm_name.strip()
                break
        
        cache[cache_key] = (target_vm_name, f"KVM virtual machine with IP {vm_ip} not found" if not target_vm_name else None)
    
    return cache[cache_key]



# 电源操作
@control_vm_bp.route('/control_vm/power', methods=['POST'])
@login_required
def power_control():
    ssh_user = os.getenv('SSH_USER')
    if not ssh_user:
        current_app.logger.info('Environment variable SSH_USER not configured')

    data = request.json
    ip = data.get('ip')
    action = data.get('action')



    vm = VM.query.options(joinedload(VM.host)).filter_by(vm_ip=ip).first()


    host_ip = vm.host.host_info.split('_')[0]
    host_type = vm.host.virtualization_type
    log_status = 'failed'
    log_details = ""
    command = None

    try:
        identifier, err = get_vm_identifier_cached(host_type, host_ip, ssh_user, ip)
        if err:
            raise Exception(err)

        command = f"sudo qm {action} {identifier}" if host_type == 'pve' else f"sudo virsh {action} {identifier}"
        output, err, exit_status = execute_ssh_command(host_ip, ssh_user, command)

        if err and not (action == 'shutdown' and 'not running' in err.lower()):
            raise Exception(f"Command execution failed: {err} (exit code: {exit_status})")

        log_status = 'success'
        log_details = f"Operation success (command: {command})"
        # 电源操作成功日志
        current_app.logger.info(f"Power operation success: user={current_user.username}, VM_IP={ip}, host IP={host_ip}, virtualization type={host_type}, SSH user={ssh_user}, action={action}")

    except Exception as e:
        log_details = str(e)
        # 电源操作失败日志
        current_app.logger.error(f"Power operation failed: user={current_user.username}, VM_IP={ip}, host IP={host_ip}, virtualization type={host_type}, action={action}, error={log_details}")
    
    finally:
        db.session.add(OperationLog(
            username=current_user.username,
            vm_ip=vm.vm_ip,
            action=action,
            status=log_status,
            details={'message': log_details, 'command': command}
        ))
        db.session.commit()

    return jsonify({
        'status': log_status,
        'message': f'VM {ip} {action} operation {"success" if log_status=="success" else "failed"}',
        'details': log_details
    })


# 状态查询逻辑
@control_vm_bp.route('/control_vm/status', methods=['GET'])
@login_required
def get_status():
    ssh_user = os.getenv('SSH_USER') or os.getenv('VM_SSH_USER')
    ip = request.args.get('ip')
    if not ip or not ssh_user:
        current_app.logger.info('Environment variable SSH_USER not configured')

    vm = VM.query.options(joinedload(VM.host)).filter_by(vm_ip=ip).first()


    host_ip = vm.host.host_info.split('_')[0]
    host_type = vm.host.virtualization_type
    status = 'unknown'
    details = ""

    try:
        identifier, err = get_vm_identifier_cached(host_type, host_ip, ssh_user, ip)
        if err:
            raise Exception(err)

        command = f"sudo qm status {identifier}" if host_type == 'pve' else f"sudo virsh domstate {identifier}"
        output, err, _ = execute_ssh_command(host_ip, ssh_user, command)

        status = 'running' if (not err and 'running' in output.lower()) else 'stopped' if host_type == 'pve' else 'shut off'

    except Exception as e:
        details = str(e)
        # 状态查询错误日志
        current_app.logger.error(f"Status query failed: VM_IP={ip}, host IP={host_ip}, virtualization type={host_type}, SSH user={ssh_user}, error={details}")

    return jsonify({
        'status': status,
        'host_info': {'ip': host_ip, 'type': host_type, 'name': vm.host.host_info},
        'vm_info': {'ip': ip, 'identifier': identifier, 'details': details}
    })


# 页面渲染
@control_vm_bp.route('/control_vm/', methods=['GET'])
@login_required
def index():
    ip = request.args.get('ip', '').strip()
    results = []
    error = None

    if ip:
        if not re.match(r"^((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$", ip):
            error = "Please enter a valid IPv4 address"
        else:
            results = VM.query.options(joinedload(VM.host)).filter_by(vm_ip=ip).all()
            if not results:
                error = f"No VM with IP {ip} found"

    return render_template(
        'control_vm.html',
        ip=ip,
        results=results,
        error=error,
        active_page='control'
    )
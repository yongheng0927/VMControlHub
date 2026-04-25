from flask import Blueprint, render_template, request, jsonify, current_app
from flask_login import login_required, current_user
from sqlalchemy.orm import joinedload
from app.models import db, VM, OperationLog
from app.services.permission_service import role_required
from app.utils.ssh_helper import execute_ssh_command, get_ssh_user
from app.utils.cache_manager import get_vm, set_vm, delayed_delete_vm, CacheTTL
from app.utils.valkey_client import serialize_sqlalchemy_object, wrap_dict_to_object
import os
import re
import json
from datetime import datetime

control_vm_bp = Blueprint('control_vm', __name__, url_prefix='/')


def get_vm_status_from_host(vm):
    """从宿主机获取 VM 状态（通过 SSH）"""
    ssh_user = get_ssh_user()
    if not ssh_user:
        return 'unknown', None, f"SSH_USER environment variable not configured"
    
    host_ip = vm.host.host_ipaddress
    ssh_port = vm.host.ssh_port
    host_type = vm.host.virtualization_type
    vm_ip = vm.vm_ip
    
    try:
        # 先获取 VM 标识符
        if host_type == 'pve':
            output, err, _ = execute_ssh_command(host_ip, "sudo qm list", ssh_user, port=ssh_port)
            if err:
                return 'unknown', None, f"Failed to get PVE list: {err}"
            
            vmid = None
            for line in output.split('\n'):
                if re.search(r'\b' + re.escape(vm_ip) + r'\b', line):
                    vmid = line.strip().split()[0]
                    break
            
            if not vmid:
                return 'unknown', None, f"PVE VM with IP {vm_ip} not found"
            
            # 获取状态
            command = f"sudo qm status {vmid}"
            output, err, _ = execute_ssh_command(host_ip, command, ssh_user, port=ssh_port)
            if err:
                return 'unknown', vmid, f"Failed to get VM status: {err}"
            
            status = 'running' if 'running' in output.lower() else 'stopped'
            return status, vmid, None
        
        elif host_type == 'kvm':
            output, err, _ = execute_ssh_command(host_ip, "sudo virsh list --all --name", ssh_user, port=ssh_port)
            if err:
                return 'unknown', None, f"Failed to get KVM list: {err}"
            
            target_vm_name = None
            ip_pattern = re.escape(vm_ip) + r'-'
            for vm_name in output.strip().split('\n'):
                if vm_name.strip() and re.match(ip_pattern, vm_name.strip()):
                    target_vm_name = vm_name.strip()
                    break
            
            if not target_vm_name:
                return 'unknown', None, f"KVM virtual machine with IP {vm_ip} not found"
            
            # 获取状态
            command = f"sudo virsh domstate {target_vm_name}"
            output, err, _ = execute_ssh_command(host_ip, command, ssh_user, port=ssh_port)
            if err:
                return 'unknown', target_vm_name, f"Failed to get VM status: {err}"
            
            status = 'running' if 'running' in output.lower() else 'shut off'
            return status, target_vm_name, None
        
        else:
            return 'unknown', None, f"Unsupported virtualization type: {host_type}"
    
    except Exception as e:
        return 'unknown', None, str(e)


def get_vm_info_cached(vm):
    """获取 VM 信息，优先从缓存读取（与 vms 路由共享同一份缓存），缓存未命中则通过 SSH 查询并更新缓存"""
    # 使用与 vms 路由完全相同的缓存格式：键为 vm:{id}，值为序列化的 SQLAlchemy 对象
    cached_vm_data = get_vm(vm.id)
    
    if cached_vm_data is not None:
        current_app.logger.debug(f"[CACHE] HIT key=vm:{vm.id}")
        # 从缓存数据中提取状态
        status = cached_vm_data.get('status', 'unknown')
        identifier = cached_vm_data.get('identifier')
        return status, identifier, None, cached_vm_data
    
    # 缓存未命中，通过 SSH 查询状态
    current_app.logger.debug(f"[CACHE] MISS key=vm:{vm.id}, fetching from host")
    
    status, identifier, error = get_vm_status_from_host(vm)
    
    if not error:
        # 序列化 VM 对象（与 vms 路由相同格式）
        serialized = serialize_sqlalchemy_object(vm)
        if serialized:
            # 更新状态字段
            serialized['status'] = status
            serialized['identifier'] = identifier
            serialized['updated_at'] = datetime.now().isoformat()
            # 写入缓存（与 vms 路由共享）
            set_vm(vm.id, serialized, ttl=CacheTTL.OBJECT)
            current_app.logger.debug(f"[CACHE] SET key=vm:{vm.id} ttl={CacheTTL.OBJECT}s")
            return status, identifier, None, serialized
    
    return status, identifier, error, None



# 电源操作
@control_vm_bp.route('/control_vm/power', methods=['POST'])
@login_required
def power_control():
    ssh_user = get_ssh_user()
    if not ssh_user:
        current_app.logger.info('Environment variable SSH_USER not configured')

    data = request.json
    ip = data.get('ip')
    action = data.get('action')

    vm = VM.query.options(joinedload(VM.host)).filter_by(vm_ip=ip).first()

    # 使用 host_ipaddress 和 ssh_port 字段进行 SSH 连接
    host_ip = vm.host.host_ipaddress
    ssh_port = vm.host.ssh_port
    host_type = vm.host.virtualization_type
    log_status = 'failed'
    log_details = ""
    command = None

    try:
        # 使用缓存获取 VM 标识符
        _, identifier, err, _ = get_vm_info_cached(vm)
        if err:
            raise Exception(err)
        
        # 检查 identifier 是否为空
        if identifier is None:
            raise Exception(f"Failed to get VM identifier for IP {ip}")

        command = f"sudo qm {action} {identifier}" if host_type == 'pve' else f"sudo virsh {action} {identifier}"
        output, err, exit_status = execute_ssh_command(host_ip, command, ssh_user, port=ssh_port)

        if err and not (action == 'shutdown' and 'not running' in err.lower()):
            raise Exception(f"Command execution failed: {err} (exit code: {exit_status})")

        log_status = 'success'
        log_details = f"Operation success (command: {command})"
        current_app.logger.info(f"Power operation success: user={current_user.username}, VM_IP={ip}, host IP={host_ip}, virtualization type={host_type}, SSH user={ssh_user}, action={action}")
        
        # 电源操作成功后，删除对应 VM 的缓存（状态变化是写操作，必须双删缓存）
        delayed_delete_vm(vm.id)
        
    except Exception as e:
        log_details = str(e)
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
    ip = request.args.get('ip')
    if not ip:
        return jsonify({'status': 'error', 'message': 'IP parameter is required'})

    vm = VM.query.options(joinedload(VM.host)).filter_by(vm_ip=ip).first()
    if not vm:
        return jsonify({'status': 'error', 'message': f"No VM with IP {ip} found"})

    # 使用 host_ipaddress 和 ssh_port 字段进行 SSH 连接
    host_ip = vm.host.host_ipaddress
    ssh_port = vm.host.ssh_port
    host_type = vm.host.virtualization_type
    status = 'unknown'
    details = ""
    identifier = None

    try:
        # 使用缓存获取 VM 信息
        status, identifier, err, vm_info = get_vm_info_cached(vm)
        if err:
            details = err
            current_app.logger.warning(f"Status query with cache error: VM_IP={ip}, error={details}")

    except Exception as e:
        details = str(e)
        current_app.logger.error(f"Status query failed: VM_IP={ip}, host IP={host_ip}, port={ssh_port}, virtualization type={host_type}, error={details}")

    return jsonify({
        'status': status,
        'host_info': {'ip': host_ip, 'port': ssh_port, 'type': host_type, 'name': vm.host.host_info},
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
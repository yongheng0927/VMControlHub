# app/services/vm_status_sync_service.py

import re
import os
import time
from datetime import datetime
from flask import current_app
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from concurrent.futures import ThreadPoolExecutor, as_completed
from app.models import db, VM, Host
from app.services.log_service import log_change
from app.utils.ssh_helper import execute_ssh_command, get_ssh_user


# 创建限流器
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri="memory://",
    default_limits=["200 per day", "50 per hour"]
)

class VMStatusSyncService:
    """VM 状态同步服务（只同步状态）"""
    
    def __init__(self, ssh_user):
        self.ssh_user = ssh_user
    
    def execute_ssh_command(self, host, command, timeout=30):
        """
        执行 SSH 命令（包装函数）
        
        :param host: 宿主机 IP 或 Host 对象
        :param command: 要执行的命令
        :param timeout: 超时时间（秒）
        :return: (output, error, exit_status)
        """
        host_ip = host if isinstance(host, str) else host.split('_')[0]
        return execute_ssh_command(host_ip, command, self.ssh_user, timeout)
    
    def sync_all_vms(self, max_workers=10):
        """
        同步所有 VM 的状态（并发版本）
        
        :param max_workers: 最大并发线程数（默认 10，即同时处理 10 个宿主机）
        返回：dict: {'total': int, 'success': int, 'failed': int, 'changed': int, 'unchanged': int, 'vms': list}
        """
        vms = VM.query.all()
        
        # 按宿主机分组
        host_vms = {}
        for vm in vms:
            if vm.host:
                host_key = vm.host.host_info
                if host_key not in host_vms:
                    host_vms[host_key] = []
                host_vms[host_key].append(vm)
        
        # 结果收集（需要线程安全）
        import threading
        results_lock = threading.Lock()
        all_results = {
            'total': len(vms),
            'success': 0,
            'failed': 0,
            'changed': 0,
            'unchanged': 0,
            'vms': []
        }
        
        # 获取 Flask 应用对象（用于子线程创建上下文）
        from flask import current_app
        app = current_app._get_current_object()
        
        def process_host_wrapper(host_info, host_vm_list):
            """包装函数：在子线程中创建 Flask 应用上下文"""
            with app.app_context():
                from flask import current_app
                return process_host_impl(host_info, host_vm_list)
        
        def process_host_impl(host_info, host_vm_list):
            """处理单个宿主机的 VM（实际实现）"""
            host_type = host_vm_list[0].host.virtualization_type if host_vm_list[0].host else None
            host_ip = host_info.split('_')[0]
            
            # 本宿主机的结果
            host_results = {
                'success': 0,
                'failed': 0,
                'changed': 0,
                'unchanged': 0,
                'vms': []
            }
            
            # 预先获取宿主机的所有 VM 信息
            vm_info_map = None
            vm_list_output = None
            
            if host_type == 'pve':
                vm_info_map = self._get_all_vm_ids_and_status_pve(host_ip)
            elif host_type == 'kvm':
                vm_list_output, error, _ = self.execute_ssh_command(host_ip, "sudo virsh list --all --name")
                vm_list_output = vm_list_output if not error else None
            
            if host_type and not vm_info_map and not vm_list_output:
                # SSH 连接失败，所有 VM 状态设为 unknown
                for vm in host_vm_list:
                    old_status = vm.status
                    if old_status != 'unknown':
                        vm.status = 'unknown'
                        vm.updated_at = datetime.now()
                        
                        log_details = {
                            'old_status': old_status,
                            'new_status': 'unknown',
                            'host': host_info,
                            'sync_type': 'status_sync',
                            'error': f'Failed to connect to host {host_ip}'
                        }
                        
                        log_change(
                            'update',
                            'vm',
                            vm.vm_ip,
                            status='success',
                            detail_obj=log_details
                        )
                        
                        host_results['vms'].append({
                            'success': True,
                            'vm_ip': vm.vm_ip,
                            'old_status': old_status,
                            'new_status': 'unknown',
                            'changed': True
                        })
                        host_results['changed'] += 1
                    else:
                        host_results['vms'].append({
                            'success': True,
                            'vm_ip': vm.vm_ip,
                            'status': 'unknown',
                            'changed': False
                        })
                        host_results['unchanged'] += 1
                    host_results['success'] += 1
                
                with results_lock:
                    all_results['vms'].extend(host_results['vms'])
                    all_results['success'] += host_results['success']
                    all_results['changed'] += host_results['changed']
                    all_results['unchanged'] += host_results['unchanged']
                return
            
            # 处理每个 VM
            for vm in host_vm_list:
                try:
                    if host_type == 'pve' and vm_info_map:
                        identifier = None
                        matched_vm_data = None
                        
                        for vmid, vm_data in vm_info_map.items():
                            vm_name = vm_data.get('name', '')
                            pattern = re.escape(vm.vm_ip) + r'(-|$)'
                            if re.search(pattern, vm_name):
                                identifier = vmid
                                matched_vm_data = vm_data
                                break
                        
                        if not identifier:
                            for vmid, vm_data in vm_info_map.items():
                                vm_name = vm_data.get('name', '')
                                if vm.vm_ip in vm_name:
                                    idx = vm_name.find(vm.vm_ip)
                                    if idx >= 0:
                                        end_idx = idx + len(vm.vm_ip)
                                        if end_idx >= len(vm_name) or vm_name[end_idx] == '-':
                                            identifier = vmid
                                            matched_vm_data = vm_data
                                            break
                        
                        if not identifier:
                            # 找不到 VM，状态设为 unknown
                            old_status = vm.status
                            if old_status != 'unknown':
                                vm.status = 'unknown'
                                vm.updated_at = datetime.now()
                                
                                log_details = {
                                    'old_status': old_status,
                                    'new_status': 'unknown',
                                    'host': host_info,
                                    'sync_type': 'status_sync',
                                    'error': f'No VMID found for IP: {vm.vm_ip}'
                                }
                                
                                log_change(
                                    'update',
                                    'vm',
                                    vm.vm_ip,
                                    status='success',
                                    detail_obj=log_details
                                )
                                
                                host_results['vms'].append({
                                    'success': True,
                                    'vm_ip': vm.vm_ip,
                                    'old_status': old_status,
                                    'new_status': 'unknown',
                                    'changed': True
                                })
                                host_results['changed'] += 1
                            else:
                                host_results['vms'].append({
                                    'success': True,
                                    'vm_ip': vm.vm_ip,
                                    'status': 'unknown',
                                    'changed': False
                                })
                                host_results['unchanged'] += 1
                            host_results['success'] += 1
                            continue
                        
                        status = matched_vm_data.get('status', 'stopped')
                    
                    elif host_type == 'kvm':
                        identifier = self._get_vm_identifier_kvm(vm_list_output, vm.vm_ip)
                        
                        if not identifier:
                            # 找不到 VM，状态设为 unknown
                            old_status = vm.status
                            if old_status != 'unknown':
                                vm.status = 'unknown'
                                vm.updated_at = datetime.now()
                                
                                log_details = {
                                    'old_status': old_status,
                                    'new_status': 'unknown',
                                    'host': host_info,
                                    'sync_type': 'status_sync',
                                    'error': 'No VM name found'
                                }
                                
                                log_change(
                                    'update',
                                    'vm',
                                    vm.vm_ip,
                                    status='success',
                                    detail_obj=log_details
                                )
                                
                                host_results['vms'].append({
                                    'success': True,
                                    'vm_ip': vm.vm_ip,
                                    'old_status': old_status,
                                    'new_status': 'unknown',
                                    'changed': True
                                })
                                host_results['changed'] += 1
                            else:
                                host_results['vms'].append({
                                    'success': True,
                                    'vm_ip': vm.vm_ip,
                                    'status': 'unknown',
                                    'changed': False
                                })
                                host_results['unchanged'] += 1
                            host_results['success'] += 1
                            continue
                        
                        status_output, status_err, _ = self.execute_ssh_command(host_ip, f"sudo virsh domstate {identifier}")
                        
                        if status_err or not status_output:
                            # 获取状态失败，设为 unknown
                            old_status = vm.status
                            if old_status != 'unknown':
                                vm.status = 'unknown'
                                vm.updated_at = datetime.now()
                                
                                log_details = {
                                    'old_status': old_status,
                                    'new_status': 'unknown',
                                    'host': host_info,
                                    'sync_type': 'status_sync',
                                    'error': 'Failed to get VM status'
                                }
                                
                                log_change(
                                    'update',
                                    'vm',
                                    vm.vm_ip,
                                    status='success',
                                    detail_obj=log_details
                                )
                                
                                host_results['vms'].append({
                                    'success': True,
                                    'vm_ip': vm.vm_ip,
                                    'old_status': old_status,
                                    'new_status': 'unknown',
                                    'changed': True
                                })
                                host_results['changed'] += 1
                            else:
                                host_results['vms'].append({
                                    'success': True,
                                    'vm_ip': vm.vm_ip,
                                    'status': 'unknown',
                                    'changed': False
                                })
                                host_results['unchanged'] += 1
                            host_results['success'] += 1
                            continue
                        
                        status = 'stopped'
                        if 'running' in status_output.lower():
                            status = 'running'
                        elif 'shut off' in status_output.lower():
                            status = 'shut off'
                    else:
                        # 不支持的宿主机类型，设为 unknown
                        old_status = vm.status
                        if old_status != 'unknown':
                            vm.status = 'unknown'
                            vm.updated_at = datetime.now()
                            
                            log_details = {
                                'old_status': old_status,
                                'new_status': 'unknown',
                                'host': host_info,
                                'sync_type': 'status_sync',
                                'error': f'Unsupported host type: {host_type}'
                            }
                            
                            log_change(
                                'update',
                                'vm',
                                vm.vm_ip,
                                status='success',
                                detail_obj=log_details
                            )
                            
                            host_results['vms'].append({
                                'success': True,
                                'vm_ip': vm.vm_ip,
                                'old_status': old_status,
                                'new_status': 'unknown',
                                'changed': True
                            })
                            host_results['changed'] += 1
                        else:
                            host_results['vms'].append({
                                'success': True,
                                'vm_ip': vm.vm_ip,
                                'status': 'unknown',
                                'changed': False
                            })
                            host_results['unchanged'] += 1
                        host_results['success'] += 1
                        continue
                    
                    # 标准化状态值
                    old_status = vm.status
                    if status.lower() == 'running':
                        new_status = 'running'
                    elif status.lower() in ['stopped', 'shut off']:
                        new_status = 'stopped'
                    else:
                        new_status = 'unknown'
                    
                    status_changed = old_status != new_status
                    
                    if status_changed:
                        vm.status = new_status
                        vm.updated_at = datetime.now()
                        
                        log_details = {
                            'old_status': old_status,
                            'new_status': new_status,
                            'host': host_info,
                            'sync_type': 'status_sync'
                        }
                        
                        log_change(
                            'update',
                            'vm',
                            vm.vm_ip,
                            status='success',
                            detail_obj=log_details
                        )
                        
                        host_results['vms'].append({
                            'success': True,
                            'vm_ip': vm.vm_ip,
                            'old_status': old_status,
                            'new_status': new_status,
                            'changed': True
                        })
                        host_results['changed'] += 1
                    else:
                        host_results['vms'].append({
                            'success': True,
                            'vm_ip': vm.vm_ip,
                            'status': new_status,
                            'changed': False
                        })
                        host_results['unchanged'] += 1
                    
                    host_results['success'] += 1
                    
                except Exception as e:
                    current_app.logger.error(f"Error syncing VM {vm.vm_ip}: {e}")
                    host_results['vms'].append({
                        'success': False,
                        'error': str(e),
                        'vm_ip': vm.vm_ip
                    })
                    host_results['failed'] += 1
            
            with results_lock:
                all_results['vms'].extend(host_results['vms'])
                all_results['success'] += host_results['success']
                all_results['failed'] += host_results['failed']
                all_results['changed'] += host_results['changed']
                all_results['unchanged'] += host_results['unchanged']
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_host = {
                executor.submit(process_host_wrapper, host_info, host_vm_list): host_info 
                for host_info, host_vm_list in host_vms.items()
            }
            
            for future in as_completed(future_to_host):
                host_info = future_to_host[future]
                try:
                    future.result()
                except Exception as e:
                    current_app.logger.error(f"Host {host_info} processing failed: {e}")
        
        try:
            db.session.commit()
        except Exception as e:
            current_app.logger.error(f"Failed to commit database changes: {e}")
            db.session.rollback()
        
        return all_results
    
    def _get_all_vm_ids_and_status_pve(self, host_ip):
        """
        批量获取 PVE 宿主机上所有 VM 的状态
        
        返回：dict: {vmid: {'status': str, 'name': str}}
        """
        vm_map = {}
        
        output, error, _ = self.execute_ssh_command(host_ip, "sudo qm list")
        if error or not output:
            return vm_map
        
        lines = output.split('\n')
        for line in lines[1:]:
            parts = line.split()
            if len(parts) >= 3:
                vmid = parts[0]
                name = parts[1] if len(parts) > 1 else ''
                status = parts[2].lower()
                vm_map[vmid] = {
                    'status': status,
                    'name': name
                }
        
        return vm_map
    
    def _get_vm_identifier_kvm(self, vm_list_output, vm_ip):
        """获取 KVM VM 的标识符（name）"""
        if not vm_list_output:
            return None
        
        lines = vm_list_output.strip().split('\n')
        for line in lines:
            vm_name = line.strip()
            if vm_name and vm_ip in vm_name:
                return vm_name
        
        return None
    
    def sync_vm_status(self, vm):
        """
        同步单个 VM 的状态
        
        返回：dict: {'success': bool, 'vm_ip': str, 'changed': bool, ...}
        """
        try:
            host = vm.host
            if not host:
                return {
                    'success': False,
                    'error': 'No host associated with VM',
                    'vm_ip': vm.vm_ip
                }
            
            host_ip = host.host_info.split('_')[0]
            host_type = host.virtualization_type
            
            # 检查 SSH 连接
            test_output, test_error, _ = self.execute_ssh_command(host_ip, "echo test")
            if test_error or not test_output:
                # SSH 连接失败，设为 unknown
                old_status = vm.status
                if old_status != 'unknown':
                    vm.status = 'unknown'
                    vm.updated_at = datetime.now()
                    
                    log_details = {
                        'old_status': old_status,
                        'new_status': 'unknown',
                        'host': host.host_info,
                        'sync_type': 'status_sync',
                        'error': f'Failed to connect to host {host_ip}'
                    }
                    
                    log_change(
                        'update',
                        'vm',
                        vm.vm_ip,
                        status='success',
                        detail_obj=log_details
                    )
                    
                    db.session.commit()
                    
                    return {
                        'success': True,
                        'vm_ip': vm.vm_ip,
                        'old_status': old_status,
                        'new_status': 'unknown',
                        'changed': True
                    }
                else:
                    return {
                        'success': True,
                        'vm_ip': vm.vm_ip,
                        'status': 'unknown',
                        'changed': False
                    }
            
            identifier = None
            
            if host_type == 'pve':
                vm_info_map = self._get_all_vm_ids_and_status_pve(host_ip)
                if not vm_info_map:
                    # 获取 VM 列表失败，设为 unknown
                    old_status = vm.status
                    if old_status != 'unknown':
                        vm.status = 'unknown'
                        vm.updated_at = datetime.now()
                        
                        log_details = {
                            'old_status': old_status,
                            'new_status': 'unknown',
                            'host': host.host_info,
                            'sync_type': 'status_sync',
                            'error': f'Failed to get VM list from host {host_ip}'
                        }
                        
                        log_change(
                            'update',
                            'vm',
                            vm.vm_ip,
                            status='success',
                            detail_obj=log_details
                        )
                        
                        db.session.commit()
                        
                        return {
                            'success': True,
                            'vm_ip': vm.vm_ip,
                            'old_status': old_status,
                            'new_status': 'unknown',
                            'changed': True
                        }
                    else:
                        return {
                            'success': True,
                            'vm_ip': vm.vm_ip,
                            'status': 'unknown',
                            'changed': False
                        }
                
                identifier = None
                for vmid, vm_data in vm_info_map.items():
                    vm_name = vm_data.get('name', '')
                    import re
                    pattern = re.escape(vm.vm_ip) + r'(-|$)'
                    if re.search(pattern, vm_name):
                        identifier = vmid
                        break
                
                if not identifier:
                    for vmid, vm_data in vm_info_map.items():
                        vm_name = vm_data.get('name', '')
                        if vm.vm_ip in vm_name:
                            idx = vm_name.find(vm.vm_ip)
                            if idx >= 0:
                                end_idx = idx + len(vm.vm_ip)
                                if end_idx >= len(vm_name) or vm_name[end_idx] == '-':
                                    identifier = vmid
                                    break
                
                if not identifier:
                    # 找不到 VM，设为 unknown
                    old_status = vm.status
                    if old_status != 'unknown':
                        vm.status = 'unknown'
                        vm.updated_at = datetime.now()
                        
                        log_details = {
                            'old_status': old_status,
                            'new_status': 'unknown',
                            'host': host.host_info,
                            'sync_type': 'status_sync',
                            'error': f'No VMID found for IP: {vm.vm_ip}'
                        }
                        
                        log_change(
                            'update',
                            'vm',
                            vm.vm_ip,
                            status='success',
                            detail_obj=log_details
                        )
                        
                        db.session.commit()
                        
                        return {
                            'success': True,
                            'vm_ip': vm.vm_ip,
                            'old_status': old_status,
                            'new_status': 'unknown',
                            'changed': True
                        }
                    else:
                        return {
                            'success': True,
                            'vm_ip': vm.vm_ip,
                            'status': 'unknown',
                            'changed': False
                        }
                
                status = vm_info_map[identifier].get('status', 'stopped')
                
            elif host_type == 'kvm':
                vm_list_output, vm_list_err, _ = self.execute_ssh_command(host_ip, "sudo virsh list --all --name")
                if vm_list_err or not vm_list_output:
                    # 获取 VM 列表失败，设为 unknown
                    old_status = vm.status
                    if old_status != 'unknown':
                        vm.status = 'unknown'
                        vm.updated_at = datetime.now()
                        
                        log_details = {
                            'old_status': old_status,
                            'new_status': 'unknown',
                            'host': host.host_info,
                            'sync_type': 'status_sync',
                            'error': f'Failed to get VM list from host {host_ip}'
                        }
                        
                        log_change(
                            'update',
                            'vm',
                            vm.vm_ip,
                            status='success',
                            detail_obj=log_details
                        )
                        
                        db.session.commit()
                        
                        return {
                            'success': True,
                            'vm_ip': vm.vm_ip,
                            'old_status': old_status,
                            'new_status': 'unknown',
                            'changed': True
                        }
                    else:
                        return {
                            'success': True,
                            'vm_ip': vm.vm_ip,
                            'status': 'unknown',
                            'changed': False
                        }
                
                identifier = self._get_vm_identifier_kvm(vm_list_output, vm.vm_ip)
                
                if not identifier:
                    # 找不到 VM，设为 unknown
                    old_status = vm.status
                    if old_status != 'unknown':
                        vm.status = 'unknown'
                        vm.updated_at = datetime.now()
                        
                        log_details = {
                            'old_status': old_status,
                            'new_status': 'unknown',
                            'host': host.host_info,
                            'sync_type': 'status_sync',
                            'error': 'No VM name found'
                        }
                        
                        log_change(
                            'update',
                            'vm',
                            vm.vm_ip,
                            status='success',
                            detail_obj=log_details
                        )
                        
                        db.session.commit()
                        
                        return {
                            'success': True,
                            'vm_ip': vm.vm_ip,
                            'old_status': old_status,
                            'new_status': 'unknown',
                            'changed': True
                        }
                    else:
                        return {
                            'success': True,
                            'vm_ip': vm.vm_ip,
                            'status': 'unknown',
                            'changed': False
                        }
                
                status_output, status_err, _ = self.execute_ssh_command(host_ip, f"sudo virsh domstate {identifier}")
                
                if status_err or not status_output:
                    # 获取状态失败，设为 unknown
                    old_status = vm.status
                    if old_status != 'unknown':
                        vm.status = 'unknown'
                        vm.updated_at = datetime.now()
                        
                        log_details = {
                            'old_status': old_status,
                            'new_status': 'unknown',
                            'host': host.host_info,
                            'sync_type': 'status_sync',
                            'error': 'Failed to get VM status'
                        }
                        
                        log_change(
                            'update',
                            'vm',
                            vm.vm_ip,
                            status='success',
                            detail_obj=log_details
                        )
                        
                        db.session.commit()
                        
                        return {
                            'success': True,
                            'vm_ip': vm.vm_ip,
                            'old_status': old_status,
                            'new_status': 'unknown',
                            'changed': True
                        }
                    else:
                        return {
                            'success': True,
                            'vm_ip': vm.vm_ip,
                            'status': 'unknown',
                            'changed': False
                        }
                
                status = 'stopped'
                if 'running' in status_output.lower():
                    status = 'running'
                elif 'shut off' in status_output.lower():
                    status = 'shut off'
            else:
                # 不支持的宿主机类型，设为 unknown
                old_status = vm.status
                if old_status != 'unknown':
                    vm.status = 'unknown'
                    vm.updated_at = datetime.now()
                    
                    log_details = {
                        'old_status': old_status,
                        'new_status': 'unknown',
                        'host': host.host_info,
                        'sync_type': 'status_sync',
                        'error': f'Unsupported virtualization type: {host_type}'
                    }
                    
                    log_change(
                        'update',
                        'vm',
                        vm.vm_ip,
                        status='success',
                        detail_obj=log_details
                    )
                    
                    db.session.commit()
                    
                    return {
                        'success': True,
                        'vm_ip': vm.vm_ip,
                        'old_status': old_status,
                        'new_status': 'unknown',
                        'changed': True
                    }
                else:
                    return {
                        'success': True,
                        'vm_ip': vm.vm_ip,
                        'status': 'unknown',
                        'changed': False
                    }
            
            old_status = vm.status
            new_status = 'running' if status.lower() == 'running' else ('stopped' if status.lower() in ['stopped', 'shut off'] else 'unknown')
            status_changed = old_status != new_status
            
            if status_changed:
                vm.status = new_status
                vm.updated_at = datetime.now()
                
                log_details = {
                    'old_status': old_status,
                    'new_status': new_status,
                    'host': host.host_info,
                    'sync_type': 'status_sync'
                }
                
                log_change(
                    'update',
                    'vm',
                    vm.vm_ip,
                    status='success',
                    detail_obj=log_details
                )
                
                db.session.commit()
                
                return {
                    'success': True,
                    'vm_ip': vm.vm_ip,
                    'old_status': old_status,
                    'new_status': new_status,
                    'changed': True
                }
            else:
                return {
                    'success': True,
                    'vm_ip': vm.vm_ip,
                    'status': new_status,
                    'changed': False
                }
                
        except Exception as e:
            current_app.logger.error(f"Error syncing VM status: {e}")
            db.session.rollback()
            return {
                'success': False,
                'error': str(e),
                'vm_ip': vm.vm_ip
            }


def sync_vm_status_task():
    """
    定时任务：同步所有 VM 的状态
    每天凌晨 00:05 自动执行一次
    """
    from app import scheduler
    from flask import _app_ctx_stack
    
    # 获取当前应用上下文，如果不存在则使用 scheduler 的应用
    app = None
    if _app_ctx_stack.top:
        app = _app_ctx_stack.top.app
    else:
        # 从 scheduler 获取应用实例
        app = scheduler.app
    
    with app.app_context():
        try:
            ssh_user = get_ssh_user()
            if not ssh_user:
                current_app.logger.warning("SSH_USER not configured, skipping scheduled VM status sync")
                return
            
            sync_service = VMStatusSyncService(ssh_user)
            result = sync_service.sync_all_vms()
            
            current_app.logger.info(
                f"Scheduled VM status sync completed: "
                f"total={result['total']}, success={result['success']}, "
                f"failed={result['failed']}, changed={result['changed']}, "
                f"unchanged={result['unchanged']}"
            )
        except Exception as e:
            current_app.logger.error(f"Scheduled VM status sync failed: {e}", exc_info=True)

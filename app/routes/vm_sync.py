# app/routes/vm_sync.py

from flask import Blueprint, jsonify, request, current_app
from flask_login import login_required, current_user
from functools import wraps
from app.models import User
from app.services.vm_status_sync_service import VMStatusSyncService, limiter
from app.utils.ssh_helper import get_ssh_user

vm_sync_bp = Blueprint('vm_sync', __name__, url_prefix='/api/vm-status')


def check_manager_role(f):
    """
    装饰器：检查用户是否为 manager 或以上角色
    
    角色等级：user < manager < admin
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return jsonify({'success': False, 'error': 'Authentication required'}), 401
        
        if current_user.role not in ['manager', 'admin']:
            return jsonify({
                'success': False,
                'error': 'Permission denied. Manager role or above required.'
            }), 403
        
        return f(*args, **kwargs)
    
    return decorated_function


@vm_sync_bp.route('/sync', methods=['POST'])
@login_required
@check_manager_role
@limiter.limit("3 per minute; 20 per hour")  # 频率限制
def sync_vm_status():
    """
    手动触发 VM 状态同步
    
    权限要求：
    - 必须登录
    - manager 或 admin 角色
    
    频率限制：
    - 每分钟最多 3 次
    - 每小时最多 20 次

    """
    try:
        ssh_user = get_ssh_user()
        if not ssh_user:
            return jsonify({
                'success': False,
                'error': 'SSH_USER not configured'
            }), 500
        
        sync_service = VMStatusSyncService(ssh_user)
        result = sync_service.sync_all_vms()
        
        total = result.get('total', 0)
        success_count = result.get('success', 0)
        failed_count = result.get('failed', 0)
        changed_count = result.get('changed', 0)
        
        # 根据同步结果判断是否成功
        if failed_count > 0:
            message = f"Sync completed: {success_count}/{total} succeeded, {failed_count} failed, {changed_count} changed"
        else:
            message = f"Sync completed: {total} VMs processed, {changed_count} status changed"
        
        # 返回详细结果
        return jsonify({
            'success': failed_count == 0,
            'message': message,
            'data': {
                'total': total,
                'success': success_count,
                'failed': failed_count,
                'changed': changed_count,
                'unchanged': result.get('unchanged', 0),
                'vms': result.get('vms', [])
            }
        })
        
    except Exception as e:
        current_app.logger.error(f"VM status sync failed: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@vm_sync_bp.route('/sync/<vm_ip>', methods=['POST'])
@login_required
@check_manager_role
@limiter.limit("10 per minute; 50 per hour")  # 单个 VM 频率限制更宽松
def sync_single_vm(vm_ip):
    """
    同步单个 VM 的状态
    
    权限要求：
    - 必须登录
    - manager 或 admin 角色
    
    频率限制：
    - 每分钟最多 10 次
    - 每小时最多 50 次
    
    参数:
    - vm_ip: VM 的 IP 地址
    """
    from app.models import VM
    
    try:
        # 查找 VM
        vm = VM.query.filter_by(vm_ip=vm_ip).first()
        if not vm:
            return jsonify({
                'success': False,
                'error': f'VM {vm_ip} not found'
            }), 404
        
        # 同步状态
        ssh_user = get_ssh_user()
        if not ssh_user:
            return jsonify({
                'success': False,
                'error': 'SSH_USER not configured'
            }), 500
        
        sync_service = VMStatusSyncService(ssh_user)
        result = sync_service.sync_vm_status(vm)
        
        if result['success']:
            return jsonify({
                'success': True,
                'message': f'VM {vm_ip} status synced',
                'data': result
            })
        else:
            return jsonify({
                'success': False,
                'error': result.get('error', 'Unknown error')
            }), 500
        
    except Exception as e:
        current_app.logger.error(f"Single VM sync failed: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@vm_sync_bp.route('/status', methods=['GET'])
@login_required
def get_sync_status():
    """
    获取同步任务状态
    
    权限要求：
    - 必须登录（任意角色）
    """
    from app import scheduler
    
    try:
        jobs = scheduler.get_jobs()
        job_list = []
        
        for job in jobs:
            job_info = {
                'id': job.id,
                'name': job.name,
                'next_run_time': job.next_run_time.isoformat() if job.next_run_time else None,
                'trigger': str(job.trigger)
            }
            job_list.append(job_info)
        
        return jsonify({
            'success': True,
            'data': {
                'scheduler_running': scheduler.running,
                'jobs': job_list
            }
        })
        
    except Exception as e:
        current_app.logger.error(f"Get sync status failed: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@vm_sync_bp.route('/history', methods=['GET'])
@login_required
def get_sync_history():
    """
    获取同步历史记录（从变更日志中查询）
    
    权限要求：
    - 必须登录（任意角色）
    
    查询参数:
    - limit: 返回记录数（默认 50）
    - vm_ip: 可选，筛选特定 VM
    """
    from app.models import ChangeLog
    from datetime import datetime, timedelta
    
    try:
        limit = request.args.get('limit', 50, type=int)
        vm_ip = request.args.get('vm_ip')
        
        # 查询最近 7 天的 VM 状态同步记录
        seven_days_ago = datetime.now() - timedelta(days=7)
        
        query = ChangeLog.query.filter(
            ChangeLog.action == 'update',
            ChangeLog.object_type == 'vm',
            ChangeLog.created_at >= seven_days_ago
        )
        
        if vm_ip:
            query = query.filter(ChangeLog.object_identifier == vm_ip)
        
        # 只查询包含状态变更的日志
        logs = query.order_by(ChangeLog.created_at.desc()).limit(limit).all()
        
        history = []
        for log in logs:
            detail = log.detail_obj if log.detail_obj else {}
            # 只包含状态同步的记录
            if detail.get('sync_type') == 'status_sync':
                history.append({
                    'timestamp': log.created_at.isoformat(),
                    'vm_ip': log.object_identifier,
                    'old_status': detail.get('old_status'),
                    'new_status': detail.get('new_status'),
                    'host': detail.get('host')
                })
        
        return jsonify({
            'success': True,
            'data': {
                'total': len(history),
                'history': history
            }
        })
        
    except Exception as e:
        current_app.logger.error(f"Get sync history failed: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

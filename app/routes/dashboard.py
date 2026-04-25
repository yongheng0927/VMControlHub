# app/routes/dashboard.py

from flask import Blueprint, render_template, jsonify
from flask_login import login_required, current_user
from app.models import Host, VM, OperationLog, db
from app.services.permission_service import role_required
from sqlalchemy import func
from types import SimpleNamespace
from sqlalchemy.orm import joinedload
from app.utils.cache_manager import get_stats_data, set_stats_data, CacheTTL

dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/')




def get_dashboard_stats():
    """
    获取仪表盘统计数据（带缓存）
    使用L3层缓存：大盘统计数据缓存（TTL=60秒）
    """
    # 尝试从缓存获取
    cached_stats = get_stats_data('dashboard')
    if cached_stats is not None:
        return cached_stats
    
    # 缓存未命中，从数据库查询
    stats = {
        'total_hosts': Host.query.count(),
        'running_hosts': Host.query.filter_by(status='running').count(),
        'stopped_hosts': Host.query.filter_by(status='stopped').count(),
        'total_vms': VM.query.count(),
        'running_vms': VM.query.filter_by(status='running').count(),
        'stopped_vms': VM.query.filter_by(status='stopped').count()
    }
    
    # 写入缓存（1分钟过期）
    set_stats_data('dashboard', stats, ttl=CacheTTL.STATS)
    
    return stats


@dashboard_bp.route('/dashboard/', methods=['GET'])
@login_required
def index():
    # Admin Manager 视图
    if current_user.role in ['admin', 'manager']:
        # 使用缓存的统计数据
        stats = get_dashboard_stats()
        
        ops = (
            OperationLog.query
            .order_by(OperationLog.time.desc())
            .limit(20)
            .all()
        )
        recent_operations = []
        for op in ops:
            recent_operations.append(
                SimpleNamespace(
                    time=op.time,
                    username=op.username,
                    vm_ip=op.vm_ip,
                    operation_type=op.action,
                    status=op.status,
                )
            )

        return render_template(
            'dashboard.html',
            total_hosts=stats['total_hosts'],
            running_hosts=stats['running_hosts'],
            stopped_hosts=stats['stopped_hosts'],
            total_vms=stats['total_vms'],
            running_vms=stats['running_vms'],
            stopped_vms=stats['stopped_vms'],
            recent_operations=[op.__dict__ for op in recent_operations],
            active_page='dashboard'
        )

    # Operator 视图
    else:
        subq = (
            db.session.query(
                OperationLog.vm_ip,
                func.max(OperationLog.time).label('last_time')
            )
            .filter(OperationLog.username == current_user.username)
            .group_by(OperationLog.vm_ip)
            .order_by(func.max(OperationLog.time).desc())
            .limit(10)
            .subquery()
        )

        OL2 = OperationLog.__table__.alias('ol2')
        personal_vms_q = (
            db.session.query(
                VM.vm_ip.label('vm_ip'),
                OL2.c.action.label('last_operation'),
                subq.c.last_time.label('last_time')
            )
            .join(subq, VM.vm_ip == subq.c.vm_ip)
            .join(OL2, (OL2.c.vm_ip == subq.c.vm_ip) & (OL2.c.time == subq.c.last_time))
            .all()
        )
        personal_vms = []
        for row in personal_vms_q:
            personal_vms.append(
                {
                    'vm_ip': row.vm_ip,
                    'last_operation': row.last_operation,
                    'last_time': row.last_time
                }
            )

        ops = (
            OperationLog.query
            .filter(OperationLog.username == current_user.username)
            .order_by(OperationLog.time.desc())
            .limit(20)
            .all()
        )
        personal_operations = []
        for op in ops:
            personal_operations.append(
                {
                    'time': op.time,
                    'vm_ip': op.vm_ip,
                    'operation_type': op.action,
                    'status': op.status
                }
            )

        return render_template(
            'dashboard.html',
            personal_vms=personal_vms,
            personal_operations=personal_operations,
            active_page='dashboard'
        )
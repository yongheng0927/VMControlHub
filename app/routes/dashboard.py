# app/routes/dashboard.py

from flask import Blueprint, render_template
from flask_login import login_required, current_user
from app.models import Host, VM, OperationLog, db
from sqlalchemy import func
from types import SimpleNamespace
from sqlalchemy.orm import joinedload

dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/')




@dashboard_bp.route('/dashboard/', methods=['GET'])
@login_required
def index():
    # Admin Manager 视图
    if current_user.role in ['admin', 'manager']:
        total_hosts = Host.query.count()
        active_hosts = Host.query.filter_by(status='active').count()
        inactive_hosts = Host.query.filter_by(status='inactive').count()
        total_vms = VM.query.count()
        active_vms = VM.query.filter_by(status='active').count()
        inactive_vms = VM.query.filter_by(status='inactive').count()

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
            total_hosts=total_hosts,
            active_hosts=active_hosts,
            inactive_hosts=inactive_hosts,
            total_vms=total_vms,
            active_vms=active_vms,
            inactive_vms=inactive_vms,
            recent_operations=[op.__dict__ for op in recent_operations], # 转换为字典列表
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
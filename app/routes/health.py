# /app/routes/health.py

from flask import Blueprint, jsonify
from app.models import db
from app import APP_START_TIME
import datetime
import time
import sys

health_bp = Blueprint('health', __name__)

def format_uptime(seconds):
    """将秒数格式化为 'Xd Xh Xm Xs' 格式"""
    seconds = int(seconds)
    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    
    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    parts.append(f"{secs}s")
    
    return ' '.join(parts)

@health_bp.route('/health', methods=['GET'])
def health_check():
    """健康检查接口 - 用于验证应用服务是否正常运行"""
    # 记录请求开始时间
    request_start_time = time.time()
    
    # 计算运行时间
    current_time = time.time()
    uptime_seconds = int(current_time - APP_START_TIME)
    uptime_formatted = format_uptime(uptime_seconds)
    
    # 计算响应时间
    response_time_ms = int((time.time() - request_start_time) * 1000)
    
    return jsonify({
        'status': 'ok',
        'service': 'vmcontrolhub',
        'python_version': sys.version,
        'timestamp': datetime.datetime.now().isoformat(),
        'uptime': uptime_formatted,
        'uptime_seconds': uptime_seconds,
        'response_time_ms': response_time_ms
    }), 200

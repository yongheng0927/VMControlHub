"""
缓存统计接口

提供缓存命中率统计查询功能，用于监控和优化缓存策略

接口列表：
- GET /api/cache/stat - 获取缓存命中率统计
- POST /api/cache/stat/reset - 重置统计数据
- GET /api/cache/health - 检查缓存健康状态
"""

from flask import Blueprint, jsonify
from flask_login import login_required
from app.utils.cache_manager import CacheService

cache_stats_bp = Blueprint('cache_stats', __name__, url_prefix='/api/cache')


@cache_stats_bp.route('/stat', methods=['GET'])
@login_required
def get_cache_stat():
    """
    获取缓存命中率统计
    
    返回格式：
    {
        "cache_hit_total": 1234,
        "cache_miss_total": 456,
        "cache_hit_rate": "73.02%",
        "cache_key_count": 789
    }
    """
    cache = CacheService()
    stats = cache.get_stats()
    stats['cache_key_count'] = cache.get_key_count()
    
    return jsonify({
        'success': True,
        'data': stats
    })


@cache_stats_bp.route('/stat/reset', methods=['POST'])
@login_required
def reset_cache_stat():
    """
    重置缓存统计数据
    """
    CacheService().reset_stats()
    return jsonify({
        'success': True,
        'message': 'Cache statistics reset successfully'
    })


@cache_stats_bp.route('/health', methods=['GET'])
def cache_health_check():
    """
    检查缓存服务健康状态
    
    返回：
    {
        "available": 是否可用,
        "message": 状态消息
    }
    """
    cache = CacheService()
    available = cache.is_available()
    
    return jsonify({
        'success': True,
        'data': {
            'available': available,
            'message': 'Redis cache is available' if available else 'Redis cache is unavailable'
        }
    })

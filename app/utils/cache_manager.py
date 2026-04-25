"""
CacheService - 对象级缓存服务（对标NetBox设计）

核心设计原则：
1. 绝对禁止缓存整页分页结果
2. 只支持两种缓存Key格式：
   - 静态字典元数据：dict:xxx (如 dict:host_status)
   - 单条业务对象：host:N 或 vm:N (如 host:1, vm:100)

三层分层缓存架构：
- L1: 静态字典缓存（TTL=3600秒）- 主机状态、类型、集群下拉选项
- L2: 业务单体对象缓存（TTL=300秒）- 单条Host、单条VM
- L3: 大盘统计数据缓存（TTL=60秒）- 总主机数、总VM数等

缓存一致性：延迟双删策略
- 数据更新流程：先删缓存 → 更新数据库 → 异步延迟500ms再删一次缓存

缓存命中率统计：
- 全局内存计数器：cache_hit, cache_miss
- 提供 /api/cache/stat 接口查询统计信息
"""

import logging
import json
import threading
from typing import Optional, Any, Dict, List

from app.utils.valkey_client import serialize_sqlalchemy_object

logger = logging.getLogger(__name__)


# ==================== 缓存配置常量 ====================
class CacheTTL:
    """缓存过期时间配置（单位：秒）"""
    # L1: 静态字典元数据缓存 - 1小时
    DICT = 3600
    
    # L2: 业务单体对象缓存 - 5分钟
    OBJECT = 300
    
    # L3: 大盘统计数据缓存 - 1分钟
    STATS = 60


# ==================== 缓存统计器 ====================
class CacheStats:
    """
    缓存命中率统计器
    线程安全的内存计数器
    """
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(CacheStats, cls).__new__(cls)
                    cls._instance._init()
        return cls._instance
    
    def _init(self):
        """初始化统计计数器"""
        self._hits = 0
        self._misses = 0
        self._lock = threading.Lock()
    
    def record_hit(self):
        """记录缓存命中"""
        with self._lock:
            self._hits += 1
        logger.debug(f"CACHE HIT | Total: hits={self._hits}, misses={self._misses}")
    
    def record_miss(self):
        """记录缓存未命中"""
        with self._lock:
            self._misses += 1
        logger.debug(f"CACHE MISS | Total: hits={self._hits}, misses={self._misses}")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self._lock:
            total = self._hits + self._misses
            hit_rate = (self._hits / total * 100) if total > 0 else 0.0
            return {
                'cache_hit_total': self._hits,
                'cache_miss_total': self._misses,
                'cache_hit_rate': f"{round(hit_rate, 2)}%",
                'cache_hit_rate_value': round(hit_rate, 2)
            }
    
    def reset(self):
        """重置统计数据"""
        with self._lock:
            self._hits = 0
            self._misses = 0
        logger.info("Cache statistics reset")


# ==================== 核心缓存服务类 ====================
class CacheService:
    """
    核心缓存服务类 - 严格遵循对象级缓存原则
    
    支持的缓存操作：
    - get(key): 获取单个缓存
    - set(key, value, ttl): 设置单个缓存
    - delete(key): 删除单个缓存
    - batch_get(keys): 批量获取缓存（使用mget）
    
    缓存键命名规范：
    - 字典元数据：dict:{name}      (如 dict:host_status, dict:vm_type)
    - 主机对象：host:{id}          (如 host:1, host:2)
    - 虚拟机对象：vm:{id}          (如 vm:100, vm:101)
    - 统计数据：stats:{name}       (如 stats:dashboard)
    """
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(CacheService, cls).__new__(cls)
                    cls._instance._init()
        return cls._instance
    
    def _init(self):
        """初始化缓存服务"""
        self._redis_client = None
        self._available = False
        self._initialized = False
        self._stats = CacheStats()
        self._client_lock = threading.Lock()
    
    def _connect(self):
        """建立Redis连接（懒加载）"""
        if self._initialized:
            return
        
        with self._client_lock:
            if self._initialized:
                return
            
            try:
                import redis
                from app.config import RedisConfig
                
                redis_params = {
                    'host': RedisConfig.REDIS_HOST,
                    'port': RedisConfig.REDIS_PORT,
                    'db': RedisConfig.REDIS_DB,
                    'decode_responses': True,
                    'socket_connect_timeout': 2,
                    'socket_timeout': 2,
                    'retry_on_timeout': True
                }
                
                if RedisConfig.REDIS_PASSWORD:
                    redis_params['password'] = RedisConfig.REDIS_PASSWORD
                
                self._redis_client = redis.Redis(**redis_params)
                self._redis_client.ping()
                self._available = True
                logger.info(f"Redis connected: {RedisConfig.REDIS_HOST}:{RedisConfig.REDIS_PORT}")
                
            except ImportError:
                logger.warning("redis-py not installed, cache disabled")
            except Exception as e:
                logger.warning(f"Redis connection failed: {e}, cache disabled")
            finally:
                self._initialized = True
    
    def is_available(self) -> bool:
        """检查缓存是否可用"""
        self._connect()
        return self._available
    
    def get(self, key: str) -> Optional[Any]:
        """
        获取单个缓存值
        
        Args:
            key: 缓存键（如 host:1, vm:100, dict:host_status）
        
        Returns:
            缓存值，如果不存在返回None
        """
        if not self.is_available():
            return None
        
        try:
            value = self._redis_client.get(key)
            if value is not None:
                self._stats.record_hit()
                logger.debug(f"CACHE HIT key={key}")
                try:
                    return json.loads(value)
                except json.JSONDecodeError:
                    return value
            else:
                self._stats.record_miss()
                logger.debug(f"CACHE MISS key={key}")
                return None
        except Exception as e:
            logger.warning(f"Cache get failed key={key}: {e}")
            return None
    
    def set(self, key: str, value: Any, ttl: int = CacheTTL.OBJECT) -> bool:
        """
        设置单个缓存值
        
        Args:
            key: 缓存键
            value: 缓存值（会被JSON序列化）
            ttl: 过期时间（秒），默认300秒
        
        Returns:
            是否设置成功
        """
        if not self.is_available():
            return False
        
        try:
            serialized_value = json.dumps(value, default=str)
            self._redis_client.setex(key, ttl, serialized_value)
            logger.debug(f"CACHE SET key={key} ttl={ttl}s")
            return True
        except Exception as e:
            logger.warning(f"Cache set failed key={key}: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """
        删除单个缓存键（绝对禁止批量删除前缀！）
        
        Args:
            key: 缓存键
        
        Returns:
            是否删除成功
        """
        if not self.is_available():
            return False
        
        try:
            result = self._redis_client.delete(key)
            logger.debug(f"CACHE DELETE key={key} deleted={result > 0}")
            return result > 0
        except Exception as e:
            logger.warning(f"Cache delete failed key={key}: {e}")
            return False
    
    def batch_get(self, keys: List[str]) -> Dict[str, Any]:
        """
        批量获取缓存值（使用Redis MGET命令）
        
        Args:
            keys: 缓存键列表
        
        Returns:
            键值对字典，不存在的键不会出现在结果中
        """
        if not self.is_available() or not keys:
            return {}
        
        try:
            values = self._redis_client.mget(keys)
            result = {}
            
            for key, value in zip(keys, values):
                if value is not None:
                    self._stats.record_hit()
                    logger.debug(f"CACHE BATCH GET HIT key={key}")
                    try:
                        result[key] = json.loads(value)
                    except json.JSONDecodeError:
                        result[key] = value
                else:
                    self._stats.record_miss()
                    logger.debug(f"CACHE BATCH GET MISS key={key}")
            
            return result
        except Exception as e:
            logger.warning(f"Cache batch_get failed: {e}")
            return {}
    
    def delayed_double_delete(self, key: str, delay: float = 0.5) -> None:
        """
        延迟双删 - 保证缓存一致性
        
        执行流程：
        1. 立即删除缓存（第一次删除）
        2. 使用 threading.Timer 异步延迟执行第二次删除
        
        Args:
            key: 需要删除的缓存键
            delay: 延迟时间（秒），默认0.5秒
        """
        # 第一次删除：立即删除
        self.delete(key)
        
        # 第二次删除：异步延迟执行
        def delayed_delete():
            try:
                self.delete(key)
                logger.debug(f"DELAYED DELETE key={key}")
            except Exception as e:
                logger.warning(f"Delayed delete failed key={key}: {e}")
        
        timer = threading.Timer(delay, delayed_delete)
        timer.daemon = True
        timer.start()
        logger.debug(f"Scheduled delayed delete key={key} delay={delay}s")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        return self._stats.get_stats()
    
    def reset_stats(self):
        """重置缓存统计信息"""
        self._stats.reset()
    
    def get_key_count(self, pattern: str = "*") -> int:
        """获取匹配模式的缓存键数量（用于统计）"""
        if not self.is_available():
            return 0
        
        try:
            keys = self._redis_client.keys(pattern)
            return len(keys)
        except Exception as e:
            logger.warning(f"Failed to get key count: {e}")
            return 0


# ==================== 快捷方法（按类型封装） ====================

def get_dict(name: str) -> Optional[Any]:
    """获取字典元数据缓存（L1层）"""
    key = f"dict:{name}"
    return CacheService().get(key)


def set_dict(name: str, value: Any, ttl: int = CacheTTL.DICT) -> bool:
    """设置字典元数据缓存（L1层）"""
    key = f"dict:{name}"
    return CacheService().set(key, value, ttl)


def delete_dict(name: str) -> bool:
    """删除字典元数据缓存"""
    key = f"dict:{name}"
    return CacheService().delete(key)


def get_host(host_id: int) -> Optional[Dict]:
    """获取主机对象缓存（L2层）"""
    key = f"host:{host_id}"
    return CacheService().get(key)


def set_host(host_id: int, data: Dict, ttl: int = CacheTTL.OBJECT) -> bool:
    """设置主机对象缓存（L2层）"""
    key = f"host:{host_id}"
    # 使用 serialize_sqlalchemy_object 确保包含自定义字段
    # 如果是 SQLAlchemy 对象，会自动查询自定义字段
    # 如果是字典，会保留已有的自定义字段（如果有的话）
    serialized_data = serialize_sqlalchemy_object(data)
    return CacheService().set(key, serialized_data, ttl)


def delete_host(host_id: int) -> bool:
    """删除主机对象缓存"""
    key = f"host:{host_id}"
    return CacheService().delete(key)


def delayed_delete_host(host_id: int):
    """延迟双删主机缓存"""
    key = f"host:{host_id}"
    CacheService().delayed_double_delete(key)


def get_vm(vm_id: int) -> Optional[Dict]:
    """获取虚拟机对象缓存（L2层）"""
    key = f"vm:{vm_id}"
    return CacheService().get(key)


def set_vm(vm_id: int, data: Dict, ttl: int = CacheTTL.OBJECT) -> bool:
    """设置虚拟机对象缓存（L2层）"""
    key = f"vm:{vm_id}"
    # 使用 serialize_sqlalchemy_object 确保包含自定义字段
    serialized_data = serialize_sqlalchemy_object(data)
    return CacheService().set(key, serialized_data, ttl)


def delete_vm(vm_id: int) -> bool:
    """删除虚拟机对象缓存"""
    key = f"vm:{vm_id}"
    return CacheService().delete(key)


def delayed_delete_vm(vm_id: int):
    """延迟双删虚拟机缓存"""
    key = f"vm:{vm_id}"
    CacheService().delayed_double_delete(key)


def batch_get_hosts(host_ids: List[int]) -> Dict[int, Dict]:
    """批量获取主机对象缓存"""
    keys = [f"host:{host_id}" for host_id in host_ids]
    results = CacheService().batch_get(keys)
    return {int(k.split(':')[1]): v for k, v in results.items()}


def batch_get_vms(vm_ids: List[int]) -> Dict[int, Dict]:
    """批量获取虚拟机对象缓存"""
    keys = [f"vm:{vm_id}" for vm_id in vm_ids]
    results = CacheService().batch_get(keys)
    return {int(k.split(':')[1]): v for k, v in results.items()}


def get_stats_data(name: str) -> Optional[Any]:
    """获取统计数据缓存（L3层）"""
    key = f"stats:{name}"
    return CacheService().get(key)


def set_stats_data(name: str, value: Any, ttl: int = CacheTTL.STATS) -> bool:
    """设置统计数据缓存（L3层）"""
    key = f"stats:{name}"
    return CacheService().set(key, value, ttl)


def delete_stats(name: str) -> bool:
    """删除统计数据缓存"""
    key = f"stats:{name}"
    return CacheService().delete(key)


def invalidate_all_stats():
    """失效所有统计缓存（使用scan避免阻塞）"""
    cache = CacheService()
    if not cache.is_available():
        return
    
    try:
        cursor = 0
        deleted = 0
        while True:
            cursor, keys = cache._redis_client.scan(cursor, match="stats:*", count=100)
            if keys:
                deleted += cache._redis_client.delete(*keys)
            if cursor == 0:
                break
        logger.info(f"Invalidated {deleted} stats cache keys")
    except Exception as e:
        logger.warning(f"Failed to invalidate stats cache: {e}")


# ==================== 初始化函数 ====================

def init_cache():
    """初始化缓存服务"""
    cache = CacheService()
    cache.is_available()
    logger.info("CacheService initialized")
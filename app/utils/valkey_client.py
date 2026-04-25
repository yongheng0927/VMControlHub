import logging
import json
from typing import Optional, Any, Callable
from functools import wraps

logger = logging.getLogger(__name__)

_redis_client = None
_redis_available = False
_initialized = False


def init_valkey():
    global _redis_client, _redis_available, _initialized
    print("=== init_valkey called ===")
    try:
        import redis
        from app.config import RedisConfig
        
        print(f"Initializing Redis connection to {RedisConfig.REDIS_HOST}:{RedisConfig.REDIS_PORT}")
        
        # 构建Redis连接参数
        redis_params = {
            'host': RedisConfig.REDIS_HOST,
            'port': RedisConfig.REDIS_PORT,
            'db': RedisConfig.REDIS_DB,
            'password': RedisConfig.REDIS_PASSWORD,
            'decode_responses': True,
            'socket_connect_timeout': 2,
            'socket_timeout': 2,
            'retry_on_timeout': True
        }        
        
        print(f"Redis connection parameters: host={RedisConfig.REDIS_HOST}, port={RedisConfig.REDIS_PORT}, db={RedisConfig.REDIS_DB}")
        
        _redis_client = redis.Redis(**redis_params)
        print("Redis client created, pinging...")
        _redis_client.ping()
        _redis_available = True
        print(f"Redis connection established: {RedisConfig.REDIS_HOST}:{RedisConfig.REDIS_PORT}")
    except ImportError:
        print("redis-py not installed, cache disabled")
        _redis_client = None
        _redis_available = False
    except Exception as e:
        print(f"Redis connection failed: {e}, cache disabled")
        import traceback
        print(traceback.format_exc())
        _redis_client = None
        _redis_available = False
    finally:
        _initialized = True
        print(f"Redis initialization completed: available={_redis_available}")


def get_valkey_client():
    global _redis_client, _redis_available, _initialized
    if not _initialized:
        init_valkey()
    return _redis_client if _redis_available else None


def is_cache_available() -> bool:
    global _redis_available, _initialized
    print(f"=== is_cache_available called ===")
    if not _initialized:
        init_valkey()
    print(f"Cache available: {_redis_available}")
    return _redis_available


class CacheKeys:
    VM_INFO = "vm:info:{vm_id}"
    VM_LIST = "vm:list:{page}:{size}:{filters}"
    HOST_INFO = "host:info:{host_id}"
    HOST_LIST = "host:list:{page}:{size}:{filters}"
    HOST_VM_LIST = "host:vm:list:{host_id}"
    OPERATION_LOGS = "operation:logs:{page}:{size}"
    CHANGE_LOGS = "change:logs:{page}:{size}"
    
    @staticmethod
    def vm_info(vm_id: int) -> str:
        return CacheKeys.VM_INFO.format(vm_id=vm_id)
    
    @staticmethod
    def vm_list(page: int, size: int, filters: str = "") -> str:
        return CacheKeys.VM_LIST.format(page=page, size=size, filters=filters)
    
    @staticmethod
    def host_info(host_id: int) -> str:
        return CacheKeys.HOST_INFO.format(host_id=host_id)
    
    @staticmethod
    def host_list(page: int, size: int, filters: str = "") -> str:
        return CacheKeys.HOST_LIST.format(page=page, size=size, filters=filters)
    
    @staticmethod
    def host_vm_list(host_id: int) -> str:
        return CacheKeys.HOST_VM_LIST.format(host_id=host_id)
    
    @staticmethod
    def operation_logs(page: int, size: int) -> str:
        return CacheKeys.OPERATION_LOGS.format(page=page, size=size)
    
    @staticmethod
    def change_logs(page: int, size: int) -> str:
        return CacheKeys.CHANGE_LOGS.format(page=page, size=size)


def cache_get(key: str) -> Optional[Any]:
    client = get_valkey_client()
    if not client:
        return None
    
    try:
        value = client.get(key)
        if value:
            return json.loads(value)
        return None
    except Exception as e:
        logger.warning(f"Cache get failed for key '{key}': {e}")
        return None


def cache_set(key: str, value: Any, timeout: Optional[int] = None) -> bool:
    client = get_valkey_client()
    if not client:
        logger.info(f"Cache set failed for key '{key}': no client available")
        return False
    
    try:
        from app.config import RedisConfig
        timeout = timeout or RedisConfig.CACHE_DEFAULT_TIMEOUT
        logger.info(f"Setting cache for key '{key}' with timeout {timeout}")
        client.setex(key, timeout, json.dumps(value, default=str))
        logger.info(f"Cache set successfully for key '{key}'")
        return True
    except Exception as e:
        logger.warning(f"Cache set failed for key '{key}': {e}")
        return False


def cache_delete(key: str) -> bool:
    client = get_valkey_client()
    if not client:
        return False
    
    try:
        client.delete(key)
        return True
    except Exception as e:
        logger.warning(f"Cache delete failed for key '{key}': {e}")
        return False


def cache_delete_pattern(pattern: str) -> bool:
    client = get_valkey_client()
    if not client:
        return False
    
    try:
        keys = client.keys(pattern)
        if keys:
            client.delete(*keys)
        return True
    except Exception as e:
        logger.warning(f"Cache delete pattern failed for '{pattern}': {e}")
        return False


def invalidate_vm_cache(vm_id: Optional[int] = None):
    client = get_valkey_client()
    if not client:
        return
    
    try:
        if vm_id:
            cache_delete(CacheKeys.vm_info(vm_id))
        cache_delete_pattern("vm:list:*")
        cache_delete_pattern("host:vm:list:*")
    except Exception as e:
        logger.warning(f"Failed to invalidate VM cache: {e}")


def invalidate_host_cache(host_id: Optional[int] = None):
    client = get_valkey_client()
    if not client:
        return
    
    try:
        if host_id:
            cache_delete(CacheKeys.host_info(host_id))
            cache_delete(CacheKeys.host_vm_list(host_id))
        cache_delete_pattern("host:list:*")
        cache_delete_pattern("vm:list:*")
    except Exception as e:
        logger.warning(f"Failed to invalidate host cache: {e}")


def cached(key_builder: Callable, timeout: Optional[int] = None):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            print(f"=== cached wrapper called for function: {func.__name__} ===")
            if not is_cache_available():
                print("Cache is not available, skipping cache")
                return func(*args, **kwargs)
            
            cache_key = key_builder(*args, **kwargs)
            print(f"Generated cache key: {cache_key}")
            
            cached_result = cache_get(cache_key)
            
            if cached_result is not None:
                print(f"Cache hit for key: {cache_key}")
                return cached_result
            
            print(f"Cache miss for key: {cache_key}, calling original function")
            result = func(*args, **kwargs)
            
            if result is not None:
                print(f"Setting cache for key: {cache_key}")
                cache_set(cache_key, result, timeout)
                print(f"Cache set for key: {cache_key}")
            
            return result
        return wrapper
    return decorator


def _get_custom_field_values(resource_id: int, resource_type: str) -> dict:
    """
    获取指定资源的自定义字段值
    :param resource_id: 资源ID
    :param resource_type: 资源类型 ('host' 或 'vm')
    :return: 自定义字段值字典，key为字段ID字符串，value为字段值
    """
    try:
        from app.models import CustomFieldValue, CustomField, CustomFieldEnumOption
        
        # 获取该资源的所有自定义字段值
        field_values = CustomFieldValue.query.filter(
            CustomFieldValue.resource_type == resource_type,
            CustomFieldValue.resource_id == resource_id
        ).all()
        
        # 获取所有自定义字段配置（用于获取字段类型）
        fields = CustomField.query.filter_by(resource_type=resource_type).all()
        field_type_map = {str(f.id): f.field_type for f in fields}
        
        result = {}
        for val in field_values:
            field_type = field_type_map.get(str(val.field_id))
            if field_type == 'int':
                result[str(val.field_id)] = val.int_value
            elif field_type == 'varchar':
                result[str(val.field_id)] = val.varchar_value
            elif field_type == 'datetime':
                result[str(val.field_id)] = val.datetime_value.isoformat() if val.datetime_value else None
            elif field_type == 'enum':
                # 获取枚举选项的显示值
                enum_opt = CustomFieldEnumOption.query.filter_by(
                    field_id=val.field_id,
                    value=val.enum_value
                ).first()
                if enum_opt:
                    result[str(val.field_id)] = enum_opt.label
                else:
                    result[str(val.field_id)] = val.enum_value
            else:
                result[str(val.field_id)] = None
        
        return result
    except Exception as e:
        logger.warning(f"Failed to get custom field values for {resource_type}:{resource_id}: {e}")
        return {}


def serialize_sqlalchemy_object(obj, include_custom_fields: bool = True) -> dict:
    """
    将 SQLAlchemy 对象序列化为纯字典（去除所有方法）
    
    :param obj: SQLAlchemy 对象或其他可序列化对象
    :param include_custom_fields: 是否包含自定义字段（仅对 host 和 vm 有效）
    :return: 序列化后的字典
    """
    if obj is None:
        return None
    
    if isinstance(obj, dict):
        result = {}
        for key, value in obj.items():
            # 跳过 pagination 对象，因为它无法序列化
            if key == 'pagination' and hasattr(value, 'iter_pages'):
                continue
            result[key] = serialize_sqlalchemy_object(value, include_custom_fields)
        return result
    
    if isinstance(obj, (list, tuple)):
        return [serialize_sqlalchemy_object(item, include_custom_fields) for item in obj]
    
    if isinstance(obj, (str, bool)):
        return obj
    
    # 处理整数类型，确保整数不被转换为浮点数
    if isinstance(obj, int):
        return obj
    
    # 处理浮点数，如果是整数形式的浮点数（如 22.0），转换为整数
    if isinstance(obj, float):
        if obj.is_integer():
            return int(obj)
        return obj
    
    # 处理 Decimal 类型（数据库返回的数值可能是 Decimal 类型）
    if hasattr(obj, 'to_integral_value'):
        try:
            # 尝试转换为整数
            int_value = int(obj)
            if int_value == obj:
                return int_value
            # 否则转换为浮点数
            return float(obj)
        except:
            pass
    
    # 跳过 pagination 对象
    if hasattr(obj, 'iter_pages'):
        return None
    
    if hasattr(obj, '__table__'):
        result = {}
        table_name = obj.__table__.name
        
        for c in obj.__table__.columns:
            value = getattr(obj, c.key)
            result[c.key] = serialize_sqlalchemy_object(value, include_custom_fields)
        
        # 处理关联对象（relationships）- 只处理已加载的关联
        try:
            from sqlalchemy import inspect
            mapper = inspect(obj)
            for attr in mapper.relationships:
                # 检查关联是否已加载
                if attr in obj.__dict__:
                    related_obj = obj.__dict__[attr]
                    if related_obj is not None:
                        # 递归序列化关联对象
                        result[attr] = serialize_sqlalchemy_object(related_obj, include_custom_fields)
        except Exception:
            # 如果 inspection 失败，忽略关联对象处理
            pass
        
        # 添加自定义字段（仅对 host 和 vm 表）
        # 自定义字段需要展平到顶层，以便模板可以通过 item[field.db_field] 访问
        if include_custom_fields and table_name in ['hosts', 'vms']:
            resource_type = 'host' if table_name == 'hosts' else 'vm'
            custom_fields = _get_custom_field_values(result.get('id'), resource_type)
            if custom_fields:
                # 将自定义字段展平到顶层（字段ID作为key）
                result.update(custom_fields)
                # 同时保留 custom_fields 字典以便其他地方使用
                result['custom_fields'] = custom_fields
        
        return result
    
    try:
        return str(obj)
    except Exception:
        return None


class DictObject:
    """将字典包装成对象，使其可以用 . 访问属性"""
    def __init__(self, data):
        self._data = data
    
    def __getattr__(self, name):
        if name in self._data:
            value = self._data[name]
            if isinstance(value, dict):
                return DictObject(value)
            elif isinstance(value, list):
                return [DictObject(item) if isinstance(item, dict) else item for item in value]
            return value
        # 属性不存在时返回 None，而不是抛出异常
        return None
    
    def __getitem__(self, name):
        return self._data[name]
    
    def __contains__(self, name):
        return name in self._data
    
    def to_dict(self):
        """递归将 DictObject 转换回纯字典，用于 JSON 序列化"""
        result = {}
        for key, value in self._data.items():
            if isinstance(value, DictObject):
                result[key] = value.to_dict()
            elif isinstance(value, list):
                result[key] = [
                    item.to_dict() if isinstance(item, DictObject) else item
                    for item in value
                ]
            else:
                result[key] = value
        return result


def wrap_dict_to_object(data):
    """递归将字典（包括嵌套字典和列表）包装为 DictObject"""
    if isinstance(data, dict):
        wrapped = DictObject(data)
        # 特殊处理 items 列表
        if 'items' in data and isinstance(data['items'], list):
            wrapped._data['items'] = wrap_dict_to_object(data['items'])
        # 包装 pagination_info（如果存在）
        if 'pagination_info' in data and isinstance(data['pagination_info'], dict):
            wrapped._data['pagination_info'] = DictObject(data['pagination_info'])
        return wrapped
    elif isinstance(data, list):
        return [wrap_dict_to_object(item) for item in data]
    return data


def cache_query_data(key: str, query_func: Callable, timeout: int = 300) -> tuple:
    """
    缓存查询数据的通用函数
    
    Args:
        key: 缓存键
        query_func: 查询函数（返回 SQLAlchemy 对象列表）
        timeout: 缓存过期时间（秒）
    
    Returns:
        tuple: (数据列表，是否命中缓存)
    """
    cache_hit = False
    cached_data = cache_get(key)
    
    if cached_data is not None:
        logger.info(f"Cache hit for key: {key}")
        return cached_data, True
    
    logger.info(f"Cache miss for key: {key}, querying database")
    data = query_func()
    serialized_data = serialize_sqlalchemy_object(data)
    
    if serialized_data is not None:
        cache_set(key, serialized_data, timeout)
        logger.info(f"Cache set for key: {key} with timeout {timeout}s")
    
    return serialized_data, False

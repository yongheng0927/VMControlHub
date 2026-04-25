# app/config.py

import os

class SecretConfig:
    SECRET_KEY = os.environ.get('SECRET_KEY')

class MysqlConfig:
    MYSQL_USER = os.environ.get('MYSQL_USER')
    MYSQL_DATABASE_PORT = os.environ.get('MYSQL_DATABASE_PORT')
    MYSQL_DATABASE = os.environ.get('MYSQL_DATABASE')
    MYSQL_DATABASE_HOST = os.environ.get('MYSQL_DATABASE_HOST')
    MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD')
    SQLALCHEMY_DATABASE_URI = (
    f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}"
    f"@{MYSQL_DATABASE_HOST}:{MYSQL_DATABASE_PORT}/{MYSQL_DATABASE}"
    "?charset=utf8mb4"
    )
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "connect_args": {
            "init_command": "SET time_zone = '+08:00';",
            "charset": "utf8mb4",
            "use_unicode": True
        }
    }
    SQLALCHEMY_TRACK_MODIFICATIONS = False

class RedisConfig:
    REDIS_HOST = os.environ.get('REDIS_HOST', 'localhost')
    REDIS_PASSWORD = os.environ.get('REDIS_PASSWORD')
    REDIS_PORT = int(os.environ.get('REDIS_PORT', 6379))
    REDIS_DB = int(os.environ.get('REDIS_DB', 0))
    CACHE_DEFAULT_TIMEOUT = int(os.environ.get('CACHE_DEFAULT_TIMEOUT', 3000)) # 默认缓存过期时间：5分钟
    
    # 缓存分层TTL配置（单位：秒）
    CACHE_TTL_DICT = int(os.environ.get('CACHE_TTL_DICT', 12 * 60 * 60))      # 默认字典元数据：12小时
    CACHE_TTL_OBJECT = int(os.environ.get('CACHE_TTL_OBJECT', 30 * 60))       # 默认业务对象：30分钟
    CACHE_TTL_STATS = int(os.environ.get('CACHE_TTL_STATS', 5 * 60))          # 默认统计数据：5分钟
    
    # 延迟双删配置
    DELAYED_DELETE_SECONDS = float(os.environ.get('DELAYED_DELETE_SECONDS', 0.5))  # 默认延迟删除间隔：0.5秒

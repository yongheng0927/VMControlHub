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
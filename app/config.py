# app/config.py

import os

class SecretConfig:
    SECRET_KEY = os.environ.get('SECRET_KEY')

class MysqlConfig:
    MYSQL_DB_USER = os.environ.get('MYSQL_DB_USER')
    MYSQL_DB_PORT = os.environ.get('MYSQL_DB_PORT')
    MYSQL_DB_NAME = os.environ.get('MYSQL_DB_NAME')
    MYSQL_DB_HOST = os.environ.get('MYSQL_DB_HOST')
    MYSQL_DB_PASSWORD = os.environ.get('MYSQL_DB_PASSWORD')
    MYSQL_DB_TABLE_CHANGE_LOGS = os.environ.get('MYSQL_DB_TABLE_CHANGE_LOGS')
    MYSQL_DB_TABLE_HOSTS = os.environ.get('MYSQL_DB_TABLE_HOSTS')
    MYSQL_DB_TABLE_OPERATION_LOGS = os.environ.get('MYSQL_DB_TABLE_OPERATION_LOGS')
    MYSQL_DB_TABLE_USERS = os.environ.get('MYSQL_DB_TABLE_USERS') 
    MYSQL_DB_TABLE_VMS = os.environ.get('MYSQL_DB_TABLE_VMS')
    SQLALCHEMY_DATABASE_URI = (
    f"mysql+pymysql://{MYSQL_DB_USER}:{MYSQL_DB_PASSWORD}"
    f"@{MYSQL_DB_HOST}:{MYSQL_DB_PORT}/{MYSQL_DB_NAME}"
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
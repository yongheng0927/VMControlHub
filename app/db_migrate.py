import os
import logging
import pymysql
from pymysql.cursors import DictCursor
from sqlalchemy import inspect
from sqlalchemy.dialects.mysql import ENUM, JSON
from sqlalchemy.types import (
    Integer, BigInteger, SmallInteger, String, Text, DateTime, 
    Boolean, Float, Numeric, Date, Time, LargeBinary
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

DB_HOST = os.environ.get('MYSQL_DATABASE_HOST')
DB_PORT = int(os.environ.get('MYSQL_DATABASE_PORT'))
DB_PASSWORD = os.environ.get('MYSQL_PASSWORD')
DB_NAME = os.environ.get('MYSQL_DATABASE')
DB_USER = os.environ.get('MYSQL_USER')

def get_db_connection():
    connection = pymysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        charset='utf8mb4',
        cursorclass=DictCursor
    )
    return connection


def ensure_database_exists(connection):
    cursor = connection.cursor()
    cursor.execute(f"SHOW DATABASES LIKE '{DB_NAME}'")
    result = cursor.fetchone()
    
    if not result:
        cursor.execute(f"CREATE DATABASE `{DB_NAME}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        logger.info(f"[SUCCESS] Database '{DB_NAME}' created.")
    else:
        logger.info(f"[INFO] Database '{DB_NAME}' already exists.")
    
    cursor.execute(f"USE `{DB_NAME}`")
    connection.commit()


def get_sqlalchemy_type_string(column):
    col_type = column.type
    
    if isinstance(col_type, ENUM):
        enum_values = ", ".join(f"'{v}'" for v in col_type.enums)
        type_str = f"ENUM({enum_values})"
        if col_type.name:
            type_str += f" CHARACTER SET utf8mb4"
        return type_str
    
    elif isinstance(col_type, JSON):
        return "JSON"
    
    elif isinstance(col_type, BigInteger):
        return "BIGINT"
    
    elif isinstance(col_type, Integer):
        return "INT"
    
    elif isinstance(col_type, SmallInteger):
        return "SMALLINT"
    
    elif isinstance(col_type, String):
        length = col_type.length or 255
        return f"VARCHAR({length})"
    
    elif isinstance(col_type, Text):
        return "TEXT"
    
    elif isinstance(col_type, DateTime):
        return "DATETIME"
    
    elif isinstance(col_type, Boolean):
        return "TINYINT(1)"
    
    elif isinstance(col_type, Float):
        return "FLOAT"
    
    elif isinstance(col_type, Numeric):
        if col_type.precision and col_type.scale:
            return f"DECIMAL({col_type.precision}, {col_type.scale})"
        return "DECIMAL"
    
    elif isinstance(col_type, Date):
        return "DATE"
    
    elif isinstance(col_type, Time):
        return "TIME"
    
    elif isinstance(col_type, LargeBinary):
        length = col_type.length or 65535
        return f"BLOB"
    
    else:
        type_name = type(col_type).__name__.upper()
        return type_name


def get_server_default_value(column):
    if column.server_default is not None:
        if hasattr(column.server_default, 'arg'):
            arg = column.server_default.arg
            if hasattr(arg, 'name'):
                func_name = str(arg.name).upper()
                if func_name in ('CURRENT_TIMESTAMP', 'NOW', 'UTC_TIMESTAMP'):
                    return 'CURRENT_TIMESTAMP'
                return func_name
            elif isinstance(arg, str):
                return arg
    return None


def get_column_definition_sql(column, is_primary=False):
    type_str = get_sqlalchemy_type_string(column)
    parts = [f"`{column.name}`", type_str]
    
    if is_primary:
        parts.append("NOT NULL AUTO_INCREMENT")
    else:
        if column.nullable:
            parts.append("NULL")
        else:
            parts.append("NOT NULL")
    
    server_default = get_server_default_value(column)
    if server_default:
        if server_default == 'CURRENT_TIMESTAMP':
            parts.append("DEFAULT CURRENT_TIMESTAMP")
        else:
            parts.append(f"DEFAULT '{server_default}'")
    elif column.default is not None:
        if hasattr(column.default, 'arg'):
            default_value = column.default.arg
            if isinstance(default_value, str):
                parts.append(f"DEFAULT '{default_value}'")
            elif isinstance(default_value, (int, float)):
                parts.append(f"DEFAULT {default_value}")
            else:
                parts.append(f"DEFAULT '{default_value}'")
        else:
            parts.append(f"DEFAULT '{column.default}'")
    
    if column.comment:
        comment = column.comment.replace("'", "\\'")
        parts.append(f"COMMENT '{comment}'")
    
    return " ".join(parts)


def get_table_columns(connection, table_name):
    cursor = connection.cursor()
    cursor.execute(f"SHOW COLUMNS FROM `{table_name}`")
    columns = {}
    for row in cursor.fetchall():
        col_name = row['Field']
        col_type = row['Type']
        is_nullable = row['Null'] == 'YES'
        default = row['Default']
        columns[col_name] = {
            'type': col_type,
            'nullable': is_nullable,
            'default': default
        }
    return columns


def normalize_type_for_comparison(db_type, model_type_str):
    db_type_upper = db_type.upper().split()[0]
    model_type_upper = model_type_str.upper().split()[0]
    
    type_mappings = {
        'INT': ['INT', 'INTEGER'],
        'BIGINT': ['BIGINT'],
        'SMALLINT': ['SMALLINT', 'TINYINT'],
        'VARCHAR': ['VARCHAR'],
        'TEXT': ['TEXT', 'LONGTEXT', 'MEDIUMTEXT', 'TINYTEXT'],
        'DATETIME': ['DATETIME', 'TIMESTAMP'],
        'JSON': ['JSON', 'LONGTEXT'],
        'ENUM': ['ENUM'],
        'DATE': ['DATE'],
        'TIME': ['TIME'],
        'FLOAT': ['FLOAT', 'DOUBLE'],
        'DECIMAL': ['DECIMAL', 'NUMERIC'],
        'BLOB': ['BLOB', 'LONGBLOB', 'MEDIUMBLOB', 'TINYBLOB'],
    }
    
    for canonical, variants in type_mappings.items():
        if db_type_upper.startswith(canonical) or any(db_type_upper.startswith(v) for v in variants):
            if model_type_upper.startswith(canonical) or any(model_type_upper.startswith(v) for v in variants):
                if canonical == 'VARCHAR':
                    import re
                    db_match = re.search(r'VARCHAR\((\d+)\)', db_type_upper)
                    model_match = re.search(r'VARCHAR\((\d+)\)', model_type_upper)
                    if db_match and model_match:
                        return db_match.group(1) == model_match.group(1)
                    return True
                elif canonical == 'ENUM':
                    return True
                return True
    
    return db_type_upper.startswith(model_type_upper.split('(')[0])


def create_table_from_model(connection, model_class):
    table_name = model_class.__tablename__
    inspector = inspect(model_class)
    
    columns = []
    constraints = []
    primary_keys = inspector.primary_key
    
    # 1. 处理列定义
    for column in inspector.columns:
        is_primary = column.name in [pk.name for pk in primary_keys]
        col_def = get_column_definition_sql(column, is_primary)
        columns.append(col_def)
    
    # 2. 处理主键约束（注意：这里开头不加逗号）
    pk_names = [pk.name for pk in primary_keys]
    if pk_names:
        constraints.append(f"PRIMARY KEY (`{'`, `'.join(pk_names)}`)")
    
    # 3. 处理唯一约束（开头也不加逗号）
    for column in inspector.columns:
        if column.unique and column.name not in pk_names:
            constraints.append(f"UNIQUE KEY `unique_{column.name}` (`{column.name}`)")
    
    # 4. 合并所有部分，统一用逗号连接
    all_parts = columns + constraints
    
    create_sql = f"""
    CREATE TABLE `{table_name}` (
        {', '.join(all_parts)}
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """
    
    cursor = connection.cursor()
    cursor.execute(create_sql)
    connection.commit()
    logger.info(f"[SUCCESS] Create table [{table_name}] success.")

def get_existing_unique_keys(connection, table_name):
    """获取表中已存在的唯一索引"""
    cursor = connection.cursor()
    cursor.execute("""
        SELECT INDEX_NAME 
        FROM information_schema.STATISTICS 
        WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s AND NON_UNIQUE = 0 AND INDEX_NAME != 'PRIMARY'
    """, (DB_NAME, table_name))
    return {row['INDEX_NAME'] for row in cursor.fetchall()}


def check_and_alter_table(connection, model_class):
    table_name = model_class.__tablename__
    inspector = inspect(model_class)
    
    db_columns = get_table_columns(connection, table_name)
    model_columns = {col.name: col for col in inspector.columns}
    existing_unique_keys = get_existing_unique_keys(connection, table_name)
    
    for col_name, column in model_columns.items():
        if col_name not in db_columns:
            col_def = get_column_definition_sql(column, is_primary=False)
            alter_sql = f"ALTER TABLE `{table_name}` ADD COLUMN {col_def}"
            
            cursor = connection.cursor()
            cursor.execute(alter_sql)
            connection.commit()
            logger.info(f"[ALTER] Missing column [{col_name}] in [{table_name}]. Adding now...")
        else:
            model_type_str = get_sqlalchemy_type_string(column)
            db_col_info = db_columns[col_name]
            db_type = db_col_info['type']
            db_default = db_col_info['default']
            
            type_mismatch = not normalize_type_for_comparison(db_type, model_type_str)
            
            model_server_default = get_server_default_value(column)
            default_mismatch = False
            if model_server_default:
                if model_server_default == 'CURRENT_TIMESTAMP':
                    if db_default is not None and str(db_default).upper() != 'CURRENT_TIMESTAMP':
                        default_mismatch = True
                    elif db_default is None:
                        default_mismatch = True
                elif db_default != model_server_default:
                    default_mismatch = True
            
            if type_mismatch or default_mismatch:
                col_def = get_column_definition_sql(column, is_primary=False)
                alter_sql = f"ALTER TABLE `{table_name}` MODIFY COLUMN {col_def}"
                
                cursor = connection.cursor()
                cursor.execute(alter_sql)
                connection.commit()
                
                if type_mismatch:
                    logger.info(f"[ALTER] Column type mismatch for [{col_name}] in [{table_name}]. Modifying type...")
                else:
                    logger.info(f"[ALTER] Column default mismatch for [{col_name}] in [{table_name}]. Modifying default...")
    
    # 检查并添加缺失的唯一约束
    primary_keys = {pk.name for pk in inspector.primary_key}
    for column in inspector.columns:
        if column.unique and column.name not in primary_keys:
            index_name = f"unique_{column.name}"
            if index_name not in existing_unique_keys:
                # 在添加唯一约束之前，检查是否存在重复值
                cursor = connection.cursor()
                cursor.execute(f"""
                    SELECT `{column.name}`, COUNT(*) as count 
                    FROM `{table_name}` 
                    GROUP BY `{column.name}` 
                    HAVING COUNT(*) > 1
                """)
                duplicates = cursor.fetchall()
                
                if duplicates:
                    # 尝试自动修复：如果是 hosts 表的 host_ipaddress 字段，从 host_info 提取 IP
                    if table_name == 'hosts' and column.name == 'host_ipaddress':
                        logger.warning(f"[ALTER] Found duplicate empty values in host_ipaddress. Attempting auto-fix...")
                        # 从 host_info 字段提取 IP 地址（格式：IP_hostname）
                        cursor.execute("""
                            UPDATE hosts 
                            SET host_ipaddress = SUBSTRING_INDEX(host_info, '_', 1) 
                            WHERE host_ipaddress = '' OR host_ipaddress IS NULL
                        """)
                        connection.commit()
                        logger.info(f"[ALTER] Auto-fixed {cursor.rowcount} rows by extracting IP from host_info")
                        
                        # 再次检查是否还有重复值
                        cursor.execute("""
                            SELECT host_ipaddress, COUNT(*) as count 
                            FROM hosts 
                            GROUP BY host_ipaddress 
                            HAVING COUNT(*) > 1
                        """)
                        duplicates = cursor.fetchall()
                
                if duplicates:
                    logger.warning(f"[ALTER] Cannot add unique constraint [{index_name}] to [{table_name}] because there are duplicate values.")
                    logger.warning(f"[ALTER] Duplicate values found: {duplicates}")
                else:
                    alter_sql = f"ALTER TABLE `{table_name}` ADD UNIQUE KEY `{index_name}` (`{column.name}`)"
                    
                    cursor = connection.cursor()
                    cursor.execute(alter_sql)
                    connection.commit()
                    logger.info(f"[ALTER] Missing unique constraint [{index_name}] in [{table_name}]. Adding now...")


def table_exists(connection, table_name):
    cursor = connection.cursor()
    cursor.execute("""
        SELECT TABLE_NAME FROM information_schema.TABLES 
        WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
    """, (DB_NAME, table_name))
    result = cursor.fetchone()
    return result is not None



def run_migration():
    from app.models import db
    
    logger.info("=" * 60)
    logger.info("Starting database migration...")
    logger.info("=" * 60)
    
    try:
        connection = get_db_connection()
        logger.info("Database connection established.")
    except Exception as e:
        logger.error(f"FATAL: Failed to connect to database server: {e}")
        raise RuntimeError(f"Database connection failed: {e}")
    
    try:
        ensure_database_exists(connection)
        
        from app import models
        
        model_classes = []
        for name in dir(models):
            obj = getattr(models, name)
            if isinstance(obj, type) and hasattr(obj, '__tablename__'):
                if obj.__module__.startswith('app.models'):
                    model_classes.append(obj)
        
        for model_class in model_classes:
            table_name = model_class.__tablename__
            
            if not table_exists(connection, table_name):
                create_table_from_model(connection, model_class)
            else:
                logger.info(f"[INFO] Table [{table_name}] already exists. Checking columns...")
                check_and_alter_table(connection, model_class)
        
        
        logger.info("=" * 60)
        logger.info("Database migration completed successfully.")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"FATAL: Database migration failed: {e}")
        raise
    finally:
        connection.close()


if __name__ == '__main__':
    from dotenv import load_dotenv
    load_dotenv()
    run_migration()

# app/models.py

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.dialects.mysql import ENUM, JSON
from sqlalchemy import func
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from datetime import datetime
from app.config import MysqlConfig


db = SQLAlchemy()

class User(db.Model, UserMixin):
    __tablename__ = MysqlConfig.MYSQL_DB_TABLE_USERS

    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='用户ID,自增主键')
    username = db.Column(db.String(100), unique=True, nullable=False, comment='登录用户名,全局唯一')
    password_hash = db.Column(db.String(255), nullable=True, comment='密码哈希值,存储加密后的密码')
    temp_password = db.Column(db.String(255), nullable=True, comment='临时明文密码(仅用于首次登录)')
    role = db.Column(ENUM('admin', 'manager', 'operator', name='role_enum'), nullable=False, server_default='operator', comment='用户角色,控制权限范围')
    must_change_password = db.Column(db.Boolean, nullable=False, server_default='1', comment='密码重置标志,首次登录强制修改密码')
    created_at = db.Column(db.DateTime, nullable=False, server_default=func.current_timestamp(), comment='用户创建时间')
    last_login = db.Column(db.DateTime, nullable=True, comment='最后登录时间')
    password_last_changed = db.Column(db.DateTime, nullable=True, comment='最后密码修改时间')
    table_set = db.Column(JSON, nullable=True, comment='用户浏览器表格样式')

    def check_password(self, password):
        """验证密码(支持明文和哈希两种方式)"""
        if self.must_change_password and not self.password_hash and self.temp_password:
            return password == self.temp_password
        elif self.password_hash:
            return check_password_hash(self.password_hash, password)
        return False

    def set_password(self, new_password):
        """设置新密码(将明文转为哈希,并清空临时明文密码)"""
        self.password_hash = generate_password_hash(new_password)
        self.temp_password = None
        self.must_change_password = False
        self.password_last_changed = datetime.now()

    def __repr__(self):
        return f"<User {self.username}>"

class Host(db.Model):
    __tablename__ = MysqlConfig.MYSQL_DB_TABLE_HOSTS

    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='主机id,自增主键')
    host_info = db.Column(db.String(255), unique=True, nullable=False, comment='主机标识,格式为"ipv4_hostname"')
    virtualization_type = db.Column(ENUM('kvm', 'pve', 'other', name='virtualization_enum'), nullable=False, comment='虚拟化类型,决定管理方式')
    department = db.Column(db.String(100), nullable=False, comment='所属部门,用于权限和统计')
    status = db.Column(ENUM('active', 'inactive', name='host_status_enum'), nullable=False, server_default='active', comment='主机状态')
    created_at = db.Column(db.DateTime, nullable=False, server_default=func.current_timestamp(), comment='创建时间')
    updated_at = db.Column(db.DateTime, nullable=False, server_default=func.current_timestamp(), onupdate=func.current_timestamp(), comment='更新时间,自动维护')
    vm_count = db.Column(db.Integer, nullable=False, server_default='0', comment='宿主机关联的VM数量')

    # 关系：一个主机包含多个VM
    vms = db.relationship('VM', back_populates='host', cascade='all, delete-orphan')

    def __repr__(self):
        return f"<Host {self.host_info}>"

class VM(db.Model):
    __tablename__ = MysqlConfig.MYSQL_DB_TABLE_VMS

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True, comment='虚拟机id,自增主键')
    vm_ip = db.Column(db.String(15), unique=True, nullable=False, comment='虚拟机IP地址')
    cpus = db.Column(db.Integer, nullable=True, comment='cpu数量')
    memory_gb = db.Column(db.Integer, nullable=True, comment='内存大小(GB)')
    disk_gb = db.Column(db.Integer, nullable=True, comment='磁盘大小(GB)')
    domain_name = db.Column(db.String(20), nullable=True, comment='虚拟机域名')
    os_type = db.Column(db.String(100), nullable=False, comment='操作系统类型')
    vm_user = db.Column(db.String(100), nullable=False, comment='虚拟机登录用户名')
    host_id = db.Column(db.Integer, db.ForeignKey('hosts.id', ondelete='CASCADE'), nullable=False, comment='所属宿主机ID,关联hosts表的id')
    status = db.Column(ENUM('active', 'inactive', name='vm_status_enum'), nullable=False, server_default='active', comment='虚拟机状态')
    created_at = db.Column(db.DateTime, nullable=False, server_default=func.current_timestamp(), comment='创建时间')
    updated_at = db.Column(db.DateTime, nullable=False, server_default=func.current_timestamp(), onupdate=func.current_timestamp(), comment='更新时间,自动维护')

    # 关系：VM属于一个主机，关联多个操作日志
    host = db.relationship('Host', back_populates='vms')

    def __repr__(self):
        return f"<VM {self.vm_ip} on Host ID {self.host_id}>"

class ChangeLog(db.Model):
    __tablename__ = MysqlConfig.MYSQL_DB_TABLE_CHANGE_LOGS

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True, comment='日志ID,自增主键')
    time = db.Column(db.DateTime, nullable=False, server_default=func.current_timestamp(), comment='操作时间')
    username = db.Column(db.String(255), nullable=True, comment='执行操作的用户名(保留历史值)')  # 无外键
    action = db.Column(ENUM('create', 'update', 'delete', name='change_action_enum'), nullable=False, comment='操作类型')
    status = db.Column(ENUM('success', 'failed', name='change_status_enum'), nullable=False, comment='操作状态')
    object_type = db.Column(ENUM('host', 'vm', 'user', name='object_type_enum'), nullable=False, comment='操作对象类型')
    object_identifier = db.Column(db.String(255), nullable=False, comment='操作对象唯一标识(如IP或ID)')
    detail = db.Column(JSON, nullable=False, comment='操作详情')

    def __repr__(self):
        return f"<ChangeLog {self.id} by {self.username}>"

class OperationLog(db.Model):
    __tablename__ = MysqlConfig.MYSQL_DB_TABLE_OPERATION_LOGS

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True, comment='日志ID,自增主键')
    time = db.Column(db.DateTime, nullable=False, server_default=func.current_timestamp(), comment='操作时间')
    username = db.Column(db.String(255), nullable=True, comment='执行操作的用户名(保留历史值)')  # 无外键
    vm_ip = db.Column(db.String(15), nullable=False, comment='操作的虚拟机IP(保留历史值)')  # 无外键
    action = db.Column(ENUM('start', 'shutdown', 'reboot', name='op_action_enum'), nullable=False, comment='操作类型')
    status = db.Column(ENUM('success', 'failed', name='op_status_enum'), nullable=False, comment='操作状态')
    details = db.Column(JSON, nullable=True, comment='操作详情或错误信息')

    def __repr__(self):
        return f"<OperationLog {self.action} on {self.vm_ip} by {self.username }>"